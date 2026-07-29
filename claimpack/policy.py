"""Three-state, suppression-conscious ClaimPack policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from .canonical import canonical_bytes
from .errors import PolicyError
from .ids import sha256_label
from .records import validate_policy, validate_record
from .validate import ValidatedPack


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DimensionResult:
    result: str
    basis: tuple[str, ...]
    assessment_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "assessment_refs": list(self.assessment_refs),
            "basis": list(self.basis),
            "result": self.result,
        }


@dataclass(frozen=True)
class PolicyEvaluation:
    package_root: str
    claim_record_id: str
    claim_id: str
    policy_id: str
    policy_digest: str
    policy_as_of: str
    evaluated_at: str
    authenticated_record_ids: tuple[str, ...]
    authentication_context: str
    objection_search_complete: bool
    objection_search_context: str
    decision: Decision
    dimension_results: dict[str, DimensionResult]
    qualifications: tuple[str, ...]
    unavailable_sources: tuple[str, ...]
    ignored_records: tuple[str, ...]
    termination_reason: str
    limits_hit: tuple[str, ...]
    used_records: tuple[dict[str, Any], ...]


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timestamp lacks timezone")
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise PolicyError(f"timestamp cannot be normalized to UTC: {value}") from exc


def _issuer_matches(issuer_id: str, allowed: list[str]) -> bool:
    return "*" in allowed or issuer_id in allowed


def _is_fresh(
    assessment: dict[str, Any],
    *,
    as_of: datetime,
    max_age_days: int,
) -> bool:
    issued = _parse_timestamp(assessment["issued_at"])
    if issued > as_of:
        return False
    if as_of - issued > timedelta(days=max_age_days):
        return False
    if (
        "expires_at" in assessment
        and _parse_timestamp(assessment["expires_at"]) < as_of
    ):
        return False
    return True


def _valid_withdrawals(
    assessments: list[dict[str, Any]],
    *,
    authenticated_record_ids: set[str],
    max_events: int,
) -> tuple[set[str], set[str], dict[str, str]]:
    """Return causally valid withdrawals that have no unresolved challenge."""

    by_id = {item["record_id"]: item for item in assessments}
    candidate_by_objection: dict[str, str] = {}
    for item in assessments:
        if (
            item["record_type"] != "assessment"
            or item["assessment_kind"] != "withdrawal"
            or item["stance"] != "withdraws-prior"
            or item["record_id"] not in authenticated_record_ids
        ):
            continue
        for target_id in item["withdraws"]:
            target = by_id.get(target_id)
            if (
                target
                and target["record_type"] == "assessment"
                and target["assessment_kind"] == "objection"
                and target["issuer"]["id"] == item["issuer"]["id"]
                and target["target_claim_id"] == item["target_claim_id"]
                and _parse_timestamp(item["issued_at"])
                >= _parse_timestamp(target["issued_at"])
            ):
                candidate_by_objection[target_id] = item["record_id"]

    def withdrawal_is_effective(
        objection_id: str,
        active: frozenset[str] = frozenset(),
    ) -> bool:
        withdrawal_id = candidate_by_objection.get(objection_id)
        if (
            withdrawal_id is None
            or withdrawal_id in active
            or len(active) >= max_events
        ):
            return False
        next_active = active | {withdrawal_id}
        for challenge in assessments:
            if challenge["target"]["record_id"] != withdrawal_id:
                continue
            if challenge["assessment_kind"] == "objection":
                if withdrawal_is_effective(challenge["record_id"], next_active):
                    continue
                return False
            if challenge["assessment_kind"] in {"correction", "retraction"}:
                return False
            if challenge["outcome"] == "fail":
                return False
        return True

    withdrawn = {
        objection_id
        for objection_id in candidate_by_objection
        if withdrawal_is_effective(objection_id)
    }
    withdrawal_by_objection = {
        objection_id: candidate_by_objection[objection_id] for objection_id in withdrawn
    }
    withdrawal_records = set(withdrawal_by_objection.values())
    return withdrawn, withdrawal_records, withdrawal_by_objection


def _adverse_overlay(
    target_record_id: str,
    *,
    adverse_assessments: list[dict[str, Any]],
    withdrawal_by_objection: dict[str, str],
    policy: dict[str, Any],
    max_events: int,
) -> tuple[bool, list[dict[str, Any]], list[str], str]:
    """Collect bounded adverse overlays; only a valid withdrawal resolves an objection."""

    by_id = {item["record_id"]: item for item in adverse_assessments}
    queue = [target_record_id]
    visited_targets: set[str] = set()
    collected: dict[str, dict[str, Any]] = {}
    qualifications: list[str] = []
    blocking = False
    while queue:
        target_id = queue.pop()
        if target_id in visited_targets:
            continue
        visited_targets.add(target_id)
        if len(visited_targets) > max_events:
            return (
                False,
                list(collected.values()),
                qualifications,
                "adverse-overlay event budget exhausted",
            )
        for item in adverse_assessments:
            if item["target"]["record_id"] != target_id:
                continue
            collected[item["record_id"]] = item
            qualifications.extend(item["qualifications"])
            queue.append(item["record_id"])
            if (
                item["assessment_kind"] == "objection"
                and item["record_id"] in withdrawal_by_objection
            ):
                withdrawal = by_id.get(withdrawal_by_objection[item["record_id"]])
                if withdrawal is not None:
                    collected[withdrawal["record_id"]] = withdrawal
                    qualifications.extend(withdrawal["qualifications"])
                    queue.append(withdrawal["record_id"])
                continue
            if item["assessment_kind"] in {
                "correction",
                "objection",
                "retraction",
            } or (
                item["outcome"] == "fail"
                and _issuer_matches(
                    item["issuer"]["id"],
                    policy["adverse_issuers"],
                )
            ):
                blocking = True
    reason = (
        f"supporting record has unresolved adverse assessment: {target_record_id}"
        if blocking
        else ""
    )
    return (
        not blocking,
        list(collected.values()),
        list(dict.fromkeys(qualifications)),
        reason,
    )


def _evidence_support(
    pack: ValidatedPack,
    assessment: dict[str, Any],
    *,
    required: bool,
    require_embedded: bool,
    adverse_assessments: list[dict[str, Any]],
    withdrawal_by_objection: dict[str, str],
    policy: dict[str, Any],
    as_of: datetime,
    max_events: int,
) -> tuple[bool, list[dict[str, Any]], list[str], str]:
    """Resolve one positive assessment and its evidence without execution."""

    records: list[dict[str, Any]] = []
    qualifications: list[str] = []
    assessment_supported, overlays, overlay_qualifications, reason = _adverse_overlay(
        assessment["record_id"],
        adverse_assessments=adverse_assessments,
        withdrawal_by_objection=withdrawal_by_objection,
        policy=policy,
        max_events=max_events,
    )
    records.extend(overlays)
    qualifications.extend(overlay_qualifications)
    if not assessment_supported:
        return False, records, qualifications, reason

    references = assessment["evidence_refs"]
    if required and not references:
        return (
            False,
            records,
            qualifications,
            "positive assessment has no evidence reference",
        )

    assessment_time = _parse_timestamp(assessment["issued_at"])
    target = pack.records.get(assessment["target"]["record_id"])
    target_time = (
        _parse_timestamp(target["issued_at"])
        if target is not None and "issued_at" in target
        else None
    )
    if target_time is not None and assessment_time < target_time:
        return (
            False,
            records,
            qualifications,
            "positive assessment predates its target record",
        )
    for record_id in references:
        record = pack.records.get(record_id)
        if record is None:
            return (
                False,
                records,
                qualifications,
                f"evidence record unavailable: {record_id}",
            )
        records.append(record)
        if record["record_type"] != "evidence":
            return (
                False,
                records,
                qualifications,
                f"assessment reference is not evidence: {record_id}",
            )
        evidence_time = _parse_timestamp(record["issued_at"])
        if evidence_time > as_of:
            return (
                False,
                records,
                qualifications,
                f"supporting evidence postdates policy cutoff: {record_id}",
            )
        if evidence_time > assessment_time:
            return (
                False,
                records,
                qualifications,
                f"supporting evidence postdates its assessment: {record_id}",
            )
        if target_time is not None and evidence_time < target_time:
            return (
                False,
                records,
                qualifications,
                f"supporting evidence predates its subject record: {record_id}",
            )
        if record["subject"] != assessment["target"]:
            return (
                False,
                records,
                qualifications,
                f"evidence subject does not match assessment target: {record_id}",
            )
        if require_embedded and not any(
            artifact["embedded"] for artifact in record["artifacts"]
        ):
            return (
                False,
                records,
                qualifications,
                f"evidence has no embedded artifact: {record_id}",
            )
        qualifications.extend(record["limitations"])
        supported, overlays, overlay_qualifications, reason = _adverse_overlay(
            record_id,
            adverse_assessments=adverse_assessments,
            withdrawal_by_objection=withdrawal_by_objection,
            policy=policy,
            max_events=max_events,
        )
        records.extend(overlays)
        qualifications.extend(overlay_qualifications)
        if not supported:
            return False, records, qualifications, reason
    return True, records, list(dict.fromkeys(qualifications)), ""


def _lineage_predecessors(
    pack: ValidatedPack,
    claim: dict[str, Any],
    *,
    max_nodes: int,
) -> tuple[set[str], set[str], list[str], list[str]]:
    """Traverse explicit claim lineage transitively within a hard node budget."""

    record_ids: set[str] = set()
    claim_ids: set[str] = set()
    issues: list[str] = []
    limits: list[str] = []
    stack = [
        (item["record_id"], _parse_timestamp(claim["issued_at"]))
        for item in claim["lineage"]
    ]
    while stack:
        record_id, successor_time = stack.pop()
        if record_id in record_ids:
            continue
        record_ids.add(record_id)
        if len(record_ids) > max_nodes:
            limits.append("lineage_nodes")
            issues.append("claim-lineage node budget exhausted")
            break
        predecessor = pack.records.get(record_id)
        if predecessor is None:
            issues.append(f"claim-lineage predecessor unavailable: {record_id}")
            continue
        if predecessor["record_type"] != "claim-version":
            issues.append(f"claim-lineage predecessor has wrong type: {record_id}")
            continue
        predecessor_time = _parse_timestamp(predecessor["issued_at"])
        if predecessor_time > successor_time:
            issues.append(f"claim-lineage predecessor postdates successor: {record_id}")
        claim_ids.add(predecessor["claim_id"])
        stack.extend(
            (item["record_id"], predecessor_time) for item in predecessor["lineage"]
        )
    return record_ids, claim_ids, issues, limits


def _dependency_diagnostics(
    pack: ValidatedPack,
    claim: dict[str, Any],
    *,
    positive_assessments: list[dict[str, Any]],
    adverse_assessments: list[dict[str, Any]],
    authenticated_record_ids: set[str],
    withdrawn_objection_ids: set[str],
    withdrawal_by_objection: dict[str, str],
    max_depth: int,
    max_nodes: int,
    max_events: int,
    as_of: datetime,
    policy: dict[str, Any],
) -> tuple[str, list[str], list[str], list[str], list[str]]:
    """Check exact declared targets and their later semantic-alignment edges."""

    records = pack.records
    dependency_relations = [
        item
        for item in records.values()
        if item["record_type"] == "relation"
        and item["relation"] == "depends-on"
        and item["load_bearing"]
    ]

    visited: set[str] = set()
    stack: list[tuple[str, int, frozenset[str]]] = [
        (claim["record_id"], 0, frozenset())
    ]
    unknown = False
    reasons: list[str] = []
    used_ids: set[str] = set()
    qualifications: list[str] = []
    alignment_rule = policy["dimensions"].get(
        "semantic-scope-match",
        policy["dimensions"].get("dependency-closure"),
    )
    while stack:
        claim_id, depth, ancestors = stack.pop()
        if depth > max_depth:
            return (
                "unknown",
                ["dependency depth budget exhausted"],
                ["dependency_depth"],
                sorted(used_ids),
                list(dict.fromkeys(qualifications)),
            )
        if claim_id in ancestors:
            return (
                "unknown",
                [f"dependency cycle detected at {claim_id}"],
                ["dependency_cycle"],
                sorted(used_ids),
                list(dict.fromkeys(qualifications)),
            )
        if claim_id in visited:
            continue
        visited.add(claim_id)
        if len(visited) > max_nodes:
            return (
                "unknown",
                ["dependency node budget exhausted"],
                ["dependency_nodes"],
                sorted(used_ids),
                list(dict.fromkeys(qualifications)),
            )
        current = records.get(claim_id)
        if current is None:
            unknown = True
            reasons.append(f"dependency claim unavailable: {claim_id}")
            continue
        if current["record_type"] != "claim-version":
            return (
                "unknown",
                [f"dependency endpoint is not a claim-version: {claim_id}"],
                [],
                sorted(used_ids),
                list(dict.fromkeys(qualifications)),
            )
        used_ids.add(claim_id)
        current_time = _parse_timestamp(current["issued_at"])
        if current_time > as_of:
            unknown = True
            reasons.append(f"dependency claim postdates policy cutoff: {claim_id}")
        qualifications.extend(current["scope"]["conditions"])
        qualifications.extend(current["scope"]["exclusions"])
        qualifications.extend(current["scope"]["non_implications"])

        if claim_id != claim["record_id"]:
            (
                dependency_lineage_records,
                dependency_lineage_claims,
                dependency_lineage_issues,
                dependency_lineage_limits,
            ) = _lineage_predecessors(
                pack,
                current,
                max_nodes=max_nodes,
            )
            if dependency_lineage_limits:
                return (
                    "unknown",
                    dependency_lineage_issues,
                    dependency_lineage_limits,
                    sorted(used_ids),
                    list(dict.fromkeys(qualifications)),
                )
            if dependency_lineage_issues:
                unknown = True
                reasons.extend(dependency_lineage_issues)
            current_adverse = [
                item
                for item in adverse_assessments
                if item["target_claim_id"] == current["claim_id"]
                or (
                    item["target_claim_id"]
                    and item["target_claim_id"] in dependency_lineage_claims
                )
                or item["target"]["record_id"] in dependency_lineage_records
            ]
            current_retractions = [
                item
                for item in current_adverse
                if item["assessment_kind"] == "retraction"
                and _issuer_matches(
                    item["issuer"]["id"],
                    policy["adverse_issuers"],
                )
            ]
            current_corrections = [
                item
                for item in current_adverse
                if item["assessment_kind"] == "correction"
            ]
            current_open_objections = [
                item
                for item in current_adverse
                if item["assessment_kind"] == "objection"
                and item["stance"] == "challenges"
                and item["record_id"] not in withdrawn_objection_ids
            ]
            current_accepted_failures = [
                item
                for item in current_adverse
                if item["outcome"] == "fail"
                and _issuer_matches(
                    item["issuer"]["id"],
                    policy["adverse_issuers"],
                )
            ]
            current_adverse_context = {
                item["record_id"]: item
                for item in (
                    current_retractions
                    + current_corrections
                    + current_open_objections
                    + current_accepted_failures
                )
            }
            for item in current_adverse_context.values():
                used_ids.add(item["record_id"])
                qualifications.extend(item["qualifications"])
            if current_retractions:
                return (
                    "fail",
                    [f"dependency has an accepted retraction: {claim_id}"],
                    [],
                    sorted(used_ids),
                    list(dict.fromkeys(qualifications)),
                )
            if current_corrections:
                unknown = True
                reasons.append(f"dependency has an unresolved correction: {claim_id}")
            if current_open_objections:
                if policy["open_objection_effect"] == "deny":
                    return (
                        "fail",
                        [f"dependency has an open objection: {claim_id}"],
                        [],
                        sorted(used_ids),
                        list(dict.fromkeys(qualifications)),
                    )
                unknown = True
                reasons.append(f"dependency has an open objection: {claim_id}")

            for dimension, rule in policy["dimensions"].items():
                if not rule["required"] or dimension in {
                    "known-objections",
                }:
                    continue
                adverse_for_dimension = [
                    item
                    for item in current_adverse
                    if item["dimension"] == dimension
                    and item["outcome"] == "fail"
                    and _issuer_matches(
                        item["issuer"]["id"],
                        policy["adverse_issuers"],
                    )
                ]
                if adverse_for_dimension:
                    for item in adverse_for_dimension:
                        used_ids.add(item["record_id"])
                        qualifications.extend(item["qualifications"])
                    return (
                        "fail",
                        [
                            "dependency has an accepted adverse assessment "
                            f"for {dimension}: {claim_id}"
                        ],
                        [],
                        sorted(used_ids),
                        list(dict.fromkeys(qualifications)),
                    )

                possible_positive = [
                    item
                    for item in positive_assessments
                    if item["target"]["record_id"] == claim_id
                    and item["dimension"] == dimension
                    and item["assessment_kind"]
                    in {
                        "author-status",
                        "automated-check",
                        "correspondence",
                        "novelty-search",
                        "registry-status",
                        "reproduction",
                        "review",
                    }
                    and item["outcome"] == "pass"
                    and item["stance"] == "supports"
                    and _issuer_matches(
                        item["issuer"]["id"],
                        rule["accepted_issuers"],
                    )
                    and (
                        not policy["require_authenticated_positive"]
                        or item["record_id"] in authenticated_record_ids
                    )
                    and _parse_timestamp(item["issued_at"]) >= current_time
                ]
                supported_positive: list[dict[str, Any]] = []
                for item in possible_positive:
                    supported, evidence, evidence_qualifications, reason = (
                        _evidence_support(
                            pack,
                            item,
                            required=policy["require_evidence_for_positive"],
                            require_embedded=policy[
                                "require_embedded_evidence_for_positive"
                            ],
                            adverse_assessments=adverse_assessments,
                            withdrawal_by_objection=withdrawal_by_objection,
                            policy=policy,
                            as_of=as_of,
                            max_events=max_events,
                        )
                    )
                    for support_record in evidence:
                        used_ids.add(support_record["record_id"])
                    qualifications.extend(evidence_qualifications)
                    if not supported:
                        reasons.append(reason)
                        continue
                    supported_positive.append(item)
                    used_ids.add(item["record_id"])
                    qualifications.extend(item["qualifications"])
                if not supported_positive:
                    unknown = True
                    reasons.append(
                        "dependency lacks acceptable positive assessment "
                        f"for {dimension}: {claim_id}"
                    )

        declared_targets = {
            target["record_id"] for target in current["dependency_targets"]
        }
        outgoing = [
            relation
            for relation in dependency_relations
            if relation["source"]["record_id"] == current["record_id"]
        ]
        outgoing_targets = {relation["target"]["record_id"] for relation in outgoing}
        for undeclared in sorted(outgoing_targets - declared_targets):
            unknown = True
            reasons.append(f"load-bearing relation has undeclared target: {undeclared}")

        next_ancestors = ancestors | {claim_id}
        for target_id in sorted(declared_targets):
            matches = [
                relation
                for relation in outgoing
                if relation["target"]["record_id"] == target_id
            ]
            if not matches:
                unknown = True
                reasons.append(
                    f"semantic-alignment relation unavailable for target: {target_id}"
                )
                stack.append((target_id, depth + 1, next_ancestors))
                continue
            if len(matches) > 1:
                unknown = True
                reasons.append(
                    f"multiple load-bearing relations for target: {target_id}"
                )
            for relation in matches:
                relation_id = relation["record_id"]
                used_ids.add(relation_id)
                relation_time = _parse_timestamp(relation["issued_at"])
                target_record = records.get(target_id)
                target_time = (
                    _parse_timestamp(target_record["issued_at"])
                    if target_record is not None
                    and target_record["record_type"] == "claim-version"
                    else None
                )
                if relation_time > as_of:
                    unknown = True
                    reasons.append(
                        f"load-bearing relation postdates policy cutoff: {relation_id}"
                    )
                if relation_time < current_time or (
                    target_time is not None and relation_time < target_time
                ):
                    unknown = True
                    reasons.append(
                        f"load-bearing relation predates an endpoint: {relation_id}"
                    )
                if target_time is not None and target_time > current_time:
                    unknown = True
                    reasons.append(
                        "dependency target postdates the dependent ClaimVersion: "
                        f"{target_id}"
                    )
                alignment = relation["semantic_alignment"]["status"]
                qualifications.extend(relation["semantic_alignment"]["limitations"])
                if alignment == "contested":
                    unknown = True
                    reasons.append(
                        f"load-bearing semantic alignment is contested: {relation_id}"
                    )
                if alignment in {"partial", "unchecked"}:
                    unknown = True
                    reasons.append(f"semantic alignment is {alignment}: {relation_id}")
                relation_positive_assessments = [
                    item
                    for item in positive_assessments
                    if item["target"]["record_id"] == relation_id
                    and item["dimension"] == "semantic-scope-match"
                ]
                relation_adverse_assessments = [
                    item
                    for item in adverse_assessments
                    if item["target"]["record_id"] == relation_id
                    and item["dimension"] == "semantic-scope-match"
                ]
                relation_retractions = [
                    item
                    for item in adverse_assessments
                    if item["target"]["record_id"] == relation_id
                    and item["assessment_kind"] == "retraction"
                    and _issuer_matches(
                        item["issuer"]["id"],
                        policy["adverse_issuers"],
                    )
                ]
                relation_corrections = [
                    item
                    for item in adverse_assessments
                    if item["target"]["record_id"] == relation_id
                    and item["assessment_kind"] == "correction"
                ]
                open_alignment_objections = [
                    item
                    for item in adverse_assessments
                    if item["target"]["record_id"] == relation_id
                    and item["assessment_kind"] == "objection"
                    and item["stance"] == "challenges"
                    and item["record_id"] not in withdrawn_objection_ids
                ]
                adverse_alignment = [
                    item
                    for item in relation_adverse_assessments
                    if item["outcome"] == "fail"
                    and _issuer_matches(
                        item["issuer"]["id"],
                        policy["adverse_issuers"],
                    )
                ]
                relation_adverse_context = {
                    item["record_id"]: item
                    for item in (
                        relation_retractions
                        + relation_corrections
                        + open_alignment_objections
                        + adverse_alignment
                    )
                }
                for item in relation_adverse_context.values():
                    used_ids.add(item["record_id"])
                    qualifications.extend(item["qualifications"])
                if relation_retractions:
                    return (
                        "fail",
                        [
                            "load-bearing relation has an accepted retraction: "
                            f"{relation_id}"
                        ],
                        [],
                        sorted(used_ids),
                        list(dict.fromkeys(qualifications)),
                    )
                if relation_corrections:
                    unknown = True
                    reasons.append(
                        "load-bearing relation has an unresolved correction: "
                        f"{relation_id}"
                    )
                if open_alignment_objections:
                    if policy["open_objection_effect"] == "deny":
                        return (
                            "fail",
                            [
                                "semantic-alignment relation has an open "
                                f"objection: {relation_id}"
                            ],
                            [],
                            sorted(used_ids),
                            list(dict.fromkeys(qualifications)),
                        )
                    unknown = True
                    reasons.append(
                        "semantic-alignment relation has an open objection: "
                        f"{relation_id}"
                    )
                if adverse_alignment:
                    return (
                        "fail",
                        [
                            f"accepted alignment assessment reports failure: {relation_id}"
                        ],
                        [],
                        sorted(used_ids),
                        list(dict.fromkeys(qualifications)),
                    )
                positive_alignment = [
                    item
                    for item in relation_positive_assessments
                    if item["assessment_kind"]
                    in {
                        "automated-check",
                        "correspondence",
                        "reproduction",
                        "review",
                    }
                    if item["outcome"] == "pass"
                    and item["stance"] == "supports"
                    and alignment_rule is not None
                    and _issuer_matches(
                        item["issuer"]["id"],
                        alignment_rule["accepted_issuers"],
                    )
                    and (
                        not policy["require_authenticated_positive"]
                        or item["record_id"] in authenticated_record_ids
                    )
                    and _parse_timestamp(item["issued_at"]) >= relation_time
                ]
                supported_alignment: list[dict[str, Any]] = []
                for item in positive_alignment:
                    supported, evidence, evidence_qualifications, reason = (
                        _evidence_support(
                            pack,
                            item,
                            required=policy["require_evidence_for_positive"],
                            require_embedded=policy[
                                "require_embedded_evidence_for_positive"
                            ],
                            adverse_assessments=adverse_assessments,
                            withdrawal_by_objection=withdrawal_by_objection,
                            policy=policy,
                            as_of=as_of,
                            max_events=max_events,
                        )
                    )
                    for support_record in evidence:
                        used_ids.add(support_record["record_id"])
                    qualifications.extend(evidence_qualifications)
                    if not supported:
                        unknown = True
                        reasons.append(reason)
                        continue
                    supported_alignment.append(item)
                positive_alignment = supported_alignment
                if positive_alignment:
                    for item in positive_alignment:
                        used_ids.add(item["record_id"])
                        qualifications.extend(item["qualifications"])
                else:
                    unknown = True
                    reasons.append(
                        f"no accepted assessment of semantic alignment: {relation_id}"
                    )
            stack.append((target_id, depth + 1, next_ancestors))

    if unknown:
        return (
            "unknown",
            sorted(set(reasons)),
            [],
            sorted(used_ids),
            list(dict.fromkeys(qualifications)),
        )
    if len(visited) == 1:
        return (
            "pass",
            ["claim declares no load-bearing dependency targets"],
            [],
            sorted(used_ids),
            list(dict.fromkeys(qualifications)),
        )
    return (
        "pass",
        ["all declared dependency targets and alignment edges closed within budget"],
        [],
        sorted(used_ids),
        list(dict.fromkeys(qualifications)),
    )


def evaluate_pack(
    pack: ValidatedPack,
    policy: dict[str, Any],
    *,
    claim_record_id: str | None = None,
    as_of: datetime | None = None,
    ledger_records: list[dict[str, Any]] | None = None,
    objection_search_complete: bool = False,
    objection_search_context: str = "",
    authenticated_record_ids: set[str] | None = None,
    authentication_context: str = "",
) -> PolicyEvaluation:
    """Apply one disclosed policy without network access or execution."""

    validate_policy(policy)
    evaluated_at = datetime.now(timezone.utc)
    if as_of is None:
        as_of = evaluated_at
    elif as_of.tzinfo is None:
        raise PolicyError("as_of must include a timezone")
    as_of = as_of.astimezone(timezone.utc)
    if as_of > evaluated_at:
        raise PolicyError("policy as_of must not be later than actual evaluation time")
    claims = pack.claims()
    if claim_record_id is not None:
        claims = [item for item in claims if item["record_id"] == claim_record_id]
    elif pack.primary_claim() is not None:
        claims = [pack.primary_claim()]
    if len(claims) != 1:
        raise PolicyError(
            "policy evaluation requires exactly one selected claim-version record"
        )
    claim = claims[0]
    claim_time = _parse_timestamp(claim["issued_at"])

    authenticated_record_ids = set(authenticated_record_ids or set())
    if authenticated_record_ids and not authentication_context.strip():
        raise PolicyError(
            "authenticated record IDs require a nonempty authentication context"
        )
    if objection_search_complete and not objection_search_context.strip():
        raise PolicyError(
            "a complete objection search requires a nonempty search context"
        )
    all_assessments = [
        item for item in pack.records.values() if item["record_type"] == "assessment"
    ]
    for item in ledger_records or []:
        validate_record(item)
        if item not in adverse_records([item]):
            raise PolicyError("seen-ledger supplied a non-adverse record")
        if item["record_type"] == "assessment" and item["record_id"] not in {
            entry["record_id"] for entry in all_assessments
        }:
            all_assessments.append(item)

    assessment_ids = {item["record_id"] for item in all_assessments}
    unknown_authentication_ids = authenticated_record_ids - assessment_ids
    if unknown_authentication_ids:
        raise PolicyError(
            "authentication context identifies records not supplied to evaluation: "
            f"{sorted(unknown_authentication_ids)}"
        )

    lineage_record_ids, lineage_claim_ids, lineage_issues, lineage_limits = (
        _lineage_predecessors(
            pack,
            claim,
            max_nodes=int(policy["limits"]["dependency_nodes"]),
        )
    )
    exact_assessments = [
        item
        for item in all_assessments
        if item["target"]["record_id"] == claim["record_id"]
    ]
    same_claim_adverse = [
        item
        for item in all_assessments
        if item["target_claim_id"] == claim["claim_id"]
        and item in adverse_records([item])
    ]
    lineage_adverse = [
        item
        for item in all_assessments
        if item in adverse_records([item])
        and (
            item["target"]["record_id"] in lineage_record_ids
            or (
                item["target_claim_id"] and item["target_claim_id"] in lineage_claim_ids
            )
        )
    ]
    assessments_by_id = {
        item["record_id"]: item
        for item in exact_assessments + same_claim_adverse + lineage_adverse
    }
    assessments = list(assessments_by_id.values())

    results: dict[str, DimensionResult] = {}
    qualifications: list[str] = []
    used: dict[str, dict[str, Any]] = {claim["record_id"]: claim}
    for item in all_assessments:
        if item["record_id"] in authenticated_record_ids:
            used[item["record_id"]] = item
    limits_hit: list[str] = list(lineage_limits)
    max_age = int(policy["max_assessment_age_days"])
    not_future = [
        item for item in all_assessments if _parse_timestamp(item["issued_at"]) <= as_of
    ]
    fresh_all = [
        item
        for item in not_future
        if _is_fresh(item, as_of=as_of, max_age_days=max_age)
    ]
    fresh_ids = {item["record_id"] for item in fresh_all}
    fresh_exact = [item for item in exact_assessments if item["record_id"] in fresh_ids]
    stale_ids = sorted(
        item["record_id"] for item in assessments if item["record_id"] not in fresh_ids
    )
    assessment_limit = int(policy["limits"]["assessment_count"])
    withdrawals, withdrawal_records, withdrawal_by_objection = _valid_withdrawals(
        not_future,
        authenticated_record_ids=authenticated_record_ids,
        max_events=max(1, assessment_limit),
    )
    open_objections = [
        item
        for item in assessments
        if item in not_future
        and item["assessment_kind"] == "objection"
        and item["stance"] == "challenges"
        and item["record_id"] not in withdrawals
    ]

    assessment_budget_exhausted = len(all_assessments) > assessment_limit
    if assessment_budget_exhausted:
        limits_hit.append("assessment_count")

    dependency_result = "unknown"
    dependency_basis = ["dependency closure was not evaluated"]
    dependency_record_ids: list[str] = []
    dependency_qualifications: list[str] = []
    if policy["dimensions"].get("dependency-closure", {}).get("required"):
        (
            dependency_result,
            dependency_basis,
            dependency_limits,
            dependency_record_ids,
            dependency_qualifications,
        ) = _dependency_diagnostics(
            pack,
            claim,
            positive_assessments=fresh_all,
            adverse_assessments=not_future,
            authenticated_record_ids=authenticated_record_ids,
            withdrawn_objection_ids=withdrawals,
            withdrawal_by_objection=withdrawal_by_objection,
            max_depth=int(policy["limits"]["dependency_depth"]),
            max_nodes=int(policy["limits"]["dependency_nodes"]),
            max_events=max(1, assessment_limit),
            as_of=as_of,
            policy=policy,
        )
        limits_hit.extend(dependency_limits)
    all_assessments_by_id = {item["record_id"]: item for item in all_assessments}
    for record_id in withdrawal_records:
        if record_id in all_assessments_by_id:
            withdrawal = all_assessments_by_id[record_id]
            used[record_id] = withdrawal
            qualifications.extend(withdrawal["qualifications"])
    for record_id in dependency_record_ids:
        record = pack.records.get(record_id) or all_assessments_by_id.get(record_id)
        if record is not None:
            used[record_id] = record
    dependency_assessment_refs = tuple(
        sorted(
            record_id
            for record_id in dependency_record_ids
            if record_id in all_assessments_by_id
        )
    )
    qualifications.extend(dependency_qualifications)
    for item in assessments:
        used[item["record_id"]] = item

    global_retractions = [
        item
        for item in assessments
        if item in not_future
        and item["assessment_kind"] == "retraction"
        and _issuer_matches(item["issuer"]["id"], policy["adverse_issuers"])
    ]
    global_corrections = [
        item
        for item in assessments
        if item in not_future and item["assessment_kind"] == "correction"
    ]
    current_adverse_records = {
        item["record_id"]: item
        for item in open_objections + global_corrections + global_retractions
    }
    for item in current_adverse_records.values():
        used[item["record_id"]] = item
        qualifications.extend(item["qualifications"])

    for dimension, rule in policy["dimensions"].items():
        if not rule["required"]:
            continue

        adverse = [
            item
            for item in assessments
            if item in not_future and item["dimension"] == dimension
            if item["outcome"] == "fail"
            and _issuer_matches(item["issuer"]["id"], policy["adverse_issuers"])
        ]
        decisive_adverse = {
            item["record_id"]: item for item in adverse + global_retractions
        }
        if decisive_adverse:
            for item in decisive_adverse.values():
                used[item["record_id"]] = item
                qualifications.extend(item["qualifications"])
            results[dimension] = DimensionResult(
                "fail",
                ("accepted adverse assessment or retraction reports failure",),
                tuple(sorted(decisive_adverse)),
            )
            continue

        if open_objections:
            effect = "fail" if policy["open_objection_effect"] == "deny" else "unknown"
            refs = tuple(sorted(item["record_id"] for item in open_objections))
            for item in open_objections:
                used[item["record_id"]] = item
                qualifications.extend(item["qualifications"])
            results[dimension] = DimensionResult(
                effect,
                ("one or more open objection assessments are present",),
                refs,
            )
            continue

        if global_corrections:
            refs = tuple(sorted(item["record_id"] for item in global_corrections))
            for item in global_corrections:
                used[item["record_id"]] = item
                qualifications.extend(item["qualifications"])
            results[dimension] = DimensionResult(
                "unknown",
                ("one or more unresolved correction records are present",),
                refs,
            )
            continue

        if claim_time > as_of:
            results[dimension] = DimensionResult(
                "unknown",
                ("selected ClaimVersion postdates the policy cutoff",),
                (),
            )
            continue

        if lineage_issues:
            results[dimension] = DimensionResult(
                "unknown",
                tuple(sorted(set(lineage_issues))),
                (),
            )
            continue

        structural_basis: tuple[str, ...] = ()
        structural_refs: tuple[str, ...] = ()
        if dimension == "dependency-closure":
            if dependency_result != "pass":
                results[dimension] = DimensionResult(
                    dependency_result,
                    tuple(dependency_basis),
                    dependency_assessment_refs,
                )
                continue
            structural_basis = tuple(dependency_basis)
            structural_refs = dependency_assessment_refs

        if (
            dimension == "known-objections"
            and policy["require_complete_objection_search"]
            and not objection_search_complete
        ):
            results[dimension] = DimensionResult(
                "unknown",
                ("no sufficiently complete objection-discovery receipt was supplied",),
                (),
            )
            continue

        if assessment_budget_exhausted:
            results[dimension] = DimensionResult(
                "unknown",
                ("assessment budget exhausted; adverse records were still applied",),
                (),
            )
            continue

        candidates = [item for item in fresh_exact if item["dimension"] == dimension]

        possible_positive = [
            item
            for item in candidates
            if item["assessment_kind"]
            in {
                "author-status",
                "automated-check",
                "correspondence",
                "novelty-search",
                "registry-status",
                "reproduction",
                "review",
            }
            if item["outcome"] == "pass"
            and item["stance"] == "supports"
            and _issuer_matches(item["issuer"]["id"], rule["accepted_issuers"])
            and (
                not policy["require_authenticated_positive"]
                or item["record_id"] in authenticated_record_ids
            )
            and _parse_timestamp(item["issued_at"]) >= claim_time
        ]
        positive: list[dict[str, Any]] = []
        unsupported_reasons: list[str] = []
        for item in possible_positive:
            supported, evidence, evidence_qualifications, reason = _evidence_support(
                pack,
                item,
                required=policy["require_evidence_for_positive"],
                require_embedded=policy["require_embedded_evidence_for_positive"],
                adverse_assessments=not_future,
                withdrawal_by_objection=withdrawal_by_objection,
                policy=policy,
                as_of=as_of,
                max_events=max(1, assessment_limit),
            )
            for support_record in evidence:
                used[support_record["record_id"]] = support_record
            qualifications.extend(evidence_qualifications)
            if not supported:
                unsupported_reasons.append(reason)
                continue
            positive.append(item)
        if positive:
            for item in positive:
                used[item["record_id"]] = item
                qualifications.extend(item["qualifications"])
            results[dimension] = DimensionResult(
                "pass",
                structural_basis
                + ("explicit fresh positive assessment satisfies policy",),
                tuple(
                    sorted(
                        set(structural_refs) | {item["record_id"] for item in positive}
                    )
                ),
            )
            continue

        if unsupported_reasons:
            basis = tuple(sorted(set(unsupported_reasons)))
        elif stale_ids:
            basis = (
                "no acceptable fresh positive assessment; stale assessments exist",
            )
        else:
            basis = ("no acceptable fresh positive assessment",)
        results[dimension] = DimensionResult("unknown", basis, ())

    required_results = [item.result for item in results.values()]
    if "fail" in required_results:
        decision = Decision.DENY
    elif required_results and all(item == "pass" for item in required_results):
        decision = Decision.ALLOW
    else:
        decision = Decision.UNKNOWN

    if "dependency_cycle" in limits_hit:
        if decision is not Decision.DENY:
            decision = Decision.UNKNOWN
        termination_reason = "cycle"
    elif limits_hit:
        if decision is not Decision.DENY:
            decision = Decision.UNKNOWN
        termination_reason = "limit"
    else:
        termination_reason = "completed"

    qualifications.extend(claim["scope"]["conditions"])
    qualifications.extend(claim["scope"]["exclusions"])
    qualifications.extend(claim["scope"]["non_implications"])

    return PolicyEvaluation(
        package_root=pack.package_root,
        claim_record_id=claim["record_id"],
        claim_id=claim["claim_id"],
        policy_id=policy["policy_id"],
        policy_digest=policy["policy_digest"],
        policy_as_of=as_of.isoformat(),
        evaluated_at=evaluated_at.isoformat(),
        authenticated_record_ids=tuple(sorted(authenticated_record_ids)),
        authentication_context=authentication_context,
        objection_search_complete=objection_search_complete,
        objection_search_context=objection_search_context,
        decision=decision,
        dimension_results=results,
        qualifications=tuple(dict.fromkeys(qualifications)),
        unavailable_sources=tuple(stale_ids),
        ignored_records=tuple(
            sorted(
                item["record_id"]
                for item in all_assessments
                if item["record_id"] not in used
            )
        ),
        termination_reason=termination_reason,
        limits_hit=tuple(sorted(set(limits_hit))),
        used_records=tuple(used[key] for key in sorted(used)),
    )


def adverse_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select records whose silent disappearance could improve a decision."""

    result = []
    for item in records:
        if item.get("record_type") != "assessment":
            continue
        if item.get("outcome") == "fail" or item.get("assessment_kind") in {
            "correction",
            "objection",
            "retraction",
            "withdrawal",
        }:
            result.append(item)
    return result


def record_digest(record: dict[str, Any]) -> str:
    return sha256_label(canonical_bytes(record))

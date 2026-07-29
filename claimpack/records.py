"""Strict structural validation for ClaimPack v0.1 records."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .errors import ValidationError
from .ids import claim_id_for, package_root_for, policy_digest_for, record_id_for
from .reader import validate_relative_path

PROTOCOL_VERSION = "0.1.0"
MANIFEST_VERSION = "claimpack-manifest/0.1"

NI_RE = re.compile(r"^ni:///sha-256;[A-Za-z0-9_-]{43}$")
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

CLAIM_KINDS = {
    "asymptotic-result",
    "conditional-result",
    "conjecture",
    "counterexample",
    "finite-case",
    "formalisation-only",
    "full-result",
    "independent-reproduction",
    "partial-result",
    "rediscovery",
    "strategy-obstruction",
    "stronger-result",
    "unsupported-claim",
}

DIMENSIONS = {
    "canonical-problem-correspondence",
    "dependency-closure",
    "formal-or-certificate-verification",
    "independent-reproduction",
    "known-objections",
    "novelty-audit",
    "proof-completeness",
    "provenance-quality",
    "reproducibility",
    "semantic-scope-match",
    "statement-precision",
    "version-stability",
}

ASSESSMENT_KINDS = {
    "author-status",
    "automated-check",
    "correction",
    "correspondence",
    "novelty-search",
    "objection",
    "registry-status",
    "reproduction",
    "response",
    "retraction",
    "review",
    "withdrawal",
}

RELATIONS = {
    "cites",
    "counterexample-to",
    "depends-on",
    "equivalent-to",
    "formalizes",
    "refutes",
    "rediscovery-of",
    "reproduces",
    "specializes",
    "strengthens",
}

RECORD_TYPES = {
    "assessment",
    "claim-version",
    "evidence",
    "relation",
    "use-receipt",
}


def _error(path: str, message: str) -> ValidationError:
    return ValidationError(f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _error(path, "must be an object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise _error(path, "must be an array")
    return value


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise _error(path, "must be a string")
    if nonempty and not value:
        raise _error(path, "must not be empty")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise _error(path, "must be a boolean")
    return value


def _enum(value: Any, allowed: set[str], path: str) -> str:
    value = _string(value, path)
    if value not in allowed:
        raise _error(path, f"must be one of {sorted(allowed)}")
    return value


def _ni(value: Any, path: str) -> str:
    value = _string(value, path)
    if not NI_RE.fullmatch(value):
        raise _error(path, "must be an RFC 6920-style SHA-256 ni URI")
    return value


def _sha(value: Any, path: str) -> str:
    value = _string(value, path)
    if not SHA_RE.fullmatch(value):
        raise _error(path, "must be sha256:<64 lowercase hex characters>")
    return value


def _timestamp(value: Any, path: str) -> str:
    value = _string(value, path)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timestamp lacks timezone")
        parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise _error(path, "must be an ISO-8601 timestamp") from exc
    return value


def _closed(
    value: dict[str, Any],
    path: str,
    *,
    required: set[str],
    optional: set[str] = frozenset(),
) -> None:
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise _error(path, f"missing fields {sorted(missing)}")
    if unknown:
        raise _error(path, f"unknown fields {sorted(unknown)}")


def _strings(value: Any, path: str) -> list[str]:
    return [
        _string(item, f"{path}[{index}]")
        for index, item in enumerate(_array(value, path))
    ]


def _record_ref(value: Any, path: str) -> dict[str, Any]:
    value = _object(value, path)
    _closed(value, path, required={"record_type", "record_id"})
    _enum(value["record_type"], RECORD_TYPES, f"{path}.record_type")
    _ni(value["record_id"], f"{path}.record_id")
    return value


def _issuer(value: Any, path: str) -> dict[str, Any]:
    value = _object(value, path)
    _closed(
        value,
        path,
        required={"id", "kind", "display_name"},
        optional={"organization", "model_provider", "model_family", "run_id"},
    )
    _string(value["id"], f"{path}.id")
    _enum(
        value["kind"],
        {"ai-system", "human", "organization", "registry", "software"},
        f"{path}.kind",
    )
    _string(value["display_name"], f"{path}.display_name")
    for field in {"organization", "model_provider", "model_family", "run_id"}:
        if field in value:
            _string(value[field], f"{path}.{field}")
    return value


def _authentication(value: Any, path: str) -> dict[str, Any]:
    value = _object(value, path)
    _closed(
        value,
        path,
        required={"status"},
        optional={"method", "subject", "evidence_ref"},
    )
    _enum(
        value["status"],
        {"claimed-verified", "unverified"},
        f"{path}.status",
    )
    for field in {"method", "subject", "evidence_ref"}:
        if field in value:
            _string(value[field], f"{path}.{field}")
    return value


def _source(value: Any, path: str) -> dict[str, Any]:
    value = _object(value, path)
    _closed(
        value,
        path,
        required={"kind", "locator", "immutable"},
        optional={"digest", "version", "retrieved_at", "rights"},
    )
    _enum(
        value["kind"],
        {
            "arxiv-version",
            "doi-concept",
            "doi-version",
            "git-commit",
            "other",
            "software-heritage",
        },
        f"{path}.kind",
    )
    _string(value["locator"], f"{path}.locator")
    _boolean(value["immutable"], f"{path}.immutable")
    if "digest" in value:
        _sha(value["digest"], f"{path}.digest")
    if "version" in value:
        _string(value["version"], f"{path}.version")
    if "retrieved_at" in value:
        _timestamp(value["retrieved_at"], f"{path}.retrieved_at")
    if "rights" in value:
        _string(value["rights"], f"{path}.rights")
    return value


def _statement(value: Any, path: str) -> dict[str, Any]:
    value = _object(value, path)
    _closed(
        value,
        path,
        required={
            "definitions",
            "language",
            "latex",
            "natural",
            "quantifiers",
        },
    )
    _string(value["language"], f"{path}.language")
    _string(value["natural"], f"{path}.natural")
    _string(value["latex"], f"{path}.latex", nonempty=False)
    definitions = _array(value["definitions"], f"{path}.definitions")
    for index, definition in enumerate(definitions):
        item_path = f"{path}.definitions[{index}]"
        definition = _object(definition, item_path)
        _closed(definition, item_path, required={"term", "meaning"})
        _string(definition["term"], f"{item_path}.term")
        _string(definition["meaning"], f"{item_path}.meaning")
    _strings(value["quantifiers"], f"{path}.quantifiers")
    return value


def _scope(value: Any, path: str) -> dict[str, Any]:
    value = _object(value, path)
    _closed(
        value,
        path,
        required={
            "claim_kind",
            "conditions",
            "exclusions",
            "non_implications",
            "scope_note",
            "structured_scope",
            "targets",
        },
    )
    _enum(value["claim_kind"], CLAIM_KINDS, f"{path}.claim_kind")
    for field in {"conditions", "exclusions", "non_implications", "targets"}:
        _strings(value[field], f"{path}.{field}")
    _string(value["scope_note"], f"{path}.scope_note", nonempty=False)
    _object(value["structured_scope"], f"{path}.structured_scope")
    return value


def validate_claim_version(record: dict[str, Any]) -> None:
    path = "claim-version"
    _closed(
        record,
        path,
        required={
            "aliases",
            "claim_id",
            "claim_version",
            "dependency_targets",
            "formal_statements",
            "issued_at",
            "lineage",
            "problem_refs",
            "protocol_version",
            "provenance",
            "record_id",
            "record_type",
            "rights",
            "scope",
            "sources",
            "statement",
        },
        optional={"extensions"},
    )
    if record["protocol_version"] != PROTOCOL_VERSION:
        raise _error(
            path, f"unsupported protocol_version {record['protocol_version']!r}"
        )
    _string(record["claim_version"], f"{path}.claim_version")
    _timestamp(record["issued_at"], f"{path}.issued_at")
    _statement(record["statement"], f"{path}.statement")
    _scope(record["scope"], f"{path}.scope")
    _strings(record["aliases"], f"{path}.aliases")
    for index, target in enumerate(
        _array(record["dependency_targets"], f"{path}.dependency_targets")
    ):
        item_path = f"{path}.dependency_targets[{index}]"
        target = _record_ref(target, item_path)
        if target["record_type"] != "claim-version":
            raise _error(item_path, "dependency target must be a claim-version")

    for index, problem in enumerate(
        _array(record["problem_refs"], f"{path}.problem_refs")
    ):
        item_path = f"{path}.problem_refs[{index}]"
        problem = _object(problem, item_path)
        _closed(
            problem,
            item_path,
            required={"scheme", "id"},
            optional={"locator"},
        )
        _string(problem["scheme"], f"{item_path}.scheme")
        _string(problem["id"], f"{item_path}.id")
        if "locator" in problem:
            _string(problem["locator"], f"{item_path}.locator")

    for index, formal in enumerate(
        _array(record["formal_statements"], f"{path}.formal_statements")
    ):
        item_path = f"{path}.formal_statements[{index}]"
        formal = _object(formal, item_path)
        _closed(
            formal,
            item_path,
            required={
                "axiom_footprint",
                "build_status",
                "declaration",
                "repository_commit",
                "role",
                "source_digest",
                "system",
                "version",
            },
        )
        for field in {"system", "version", "declaration", "repository_commit"}:
            _string(formal[field], f"{item_path}.{field}")
        _enum(
            formal["role"],
            {"certificate-specification", "definition", "proof-term", "statement-only"},
            f"{item_path}.role",
        )
        _enum(
            formal["build_status"],
            {"failed", "kernel-accepted", "not-run", "unknown"},
            f"{item_path}.build_status",
        )
        _sha(formal["source_digest"], f"{item_path}.source_digest")
        _strings(formal["axiom_footprint"], f"{item_path}.axiom_footprint")

    provenance = _object(record["provenance"], f"{path}.provenance")
    _closed(provenance, f"{path}.provenance", required={"actors", "roles"})
    actors = _array(provenance["actors"], f"{path}.provenance.actors")
    actor_ids: set[str] = set()
    for index, actor in enumerate(actors):
        actor = _issuer(actor, f"{path}.provenance.actors[{index}]")
        if actor["id"] in actor_ids:
            raise _error(f"{path}.provenance.actors[{index}].id", "must be unique")
        actor_ids.add(actor["id"])
    for index, role in enumerate(
        _array(provenance["roles"], f"{path}.provenance.roles")
    ):
        item_path = f"{path}.provenance.roles[{index}]"
        role = _object(role, item_path)
        _closed(role, item_path, required={"actor_id", "role", "date"})
        if _string(role["actor_id"], f"{item_path}.actor_id") not in actor_ids:
            raise _error(f"{item_path}.actor_id", "does not identify a declared actor")
        _string(role["role"], f"{item_path}.role")
        _timestamp(role["date"], f"{item_path}.date")

    for index, source in enumerate(_array(record["sources"], f"{path}.sources")):
        _source(source, f"{path}.sources[{index}]")

    for index, lineage in enumerate(_array(record["lineage"], f"{path}.lineage")):
        item_path = f"{path}.lineage[{index}]"
        lineage = _object(lineage, item_path)
        _closed(lineage, item_path, required={"relation", "record_id"})
        _enum(
            lineage["relation"],
            {"corrects", "narrows", "revises", "strengthens", "supersedes"},
            f"{item_path}.relation",
        )
        _ni(lineage["record_id"], f"{item_path}.record_id")

    rights = _object(record["rights"], f"{path}.rights")
    _closed(rights, f"{path}.rights", required={"license", "scope", "exclusions"})
    _string(rights["license"], f"{path}.rights.license")
    _string(rights["scope"], f"{path}.rights.scope")
    _strings(rights["exclusions"], f"{path}.rights.exclusions")
    if "extensions" in record:
        _object(record["extensions"], f"{path}.extensions")

    expected_claim_id = claim_id_for(record)
    if record["claim_id"] != expected_claim_id:
        raise _error(
            f"{path}.claim_id",
            f"identity mismatch; expected {expected_claim_id}",
        )


def validate_evidence(record: dict[str, Any]) -> None:
    path = "evidence"
    _closed(
        record,
        path,
        required={
            "artifacts",
            "coverage",
            "evidence_kind",
            "issued_at",
            "issuer",
            "limitations",
            "method",
            "protocol_version",
            "record_id",
            "record_type",
            "replay",
            "subject",
        },
        optional={"extensions"},
    )
    _record_ref(record["subject"], f"{path}.subject")
    _enum(
        record["evidence_kind"],
        {
            "certificate",
            "data",
            "formal-object",
            "manuscript",
            "output",
            "replay-receipt",
            "review-material",
            "source-code",
            "transcript",
        },
        f"{path}.evidence_kind",
    )
    _timestamp(record["issued_at"], f"{path}.issued_at")
    _issuer(record["issuer"], f"{path}.issuer")
    _string(record["method"], f"{path}.method")
    _strings(record["coverage"], f"{path}.coverage")
    _strings(record["limitations"], f"{path}.limitations")
    for index, artifact in enumerate(_array(record["artifacts"], f"{path}.artifacts")):
        item_path = f"{path}.artifacts[{index}]"
        artifact = _object(artifact, item_path)
        _closed(
            artifact,
            item_path,
            required={"digest", "embedded", "media_type", "name", "rights"},
            optional={"locator", "path"},
        )
        _string(artifact["name"], f"{item_path}.name")
        _sha(artifact["digest"], f"{item_path}.digest")
        embedded = _boolean(artifact["embedded"], f"{item_path}.embedded")
        _string(artifact["media_type"], f"{item_path}.media_type")
        _string(artifact["rights"], f"{item_path}.rights")
        if embedded:
            if "path" not in artifact or "locator" in artifact:
                raise _error(
                    item_path, "embedded artifact requires path and forbids locator"
                )
            validate_relative_path(_string(artifact["path"], f"{item_path}.path"))
        else:
            if "locator" not in artifact or "path" in artifact:
                raise _error(
                    item_path, "external artifact requires locator and forbids path"
                )
            _string(artifact["locator"], f"{item_path}.locator")

    replay = _object(record["replay"], f"{path}.replay")
    _closed(
        replay,
        f"{path}.replay",
        required={
            "command",
            "display_only",
            "environment_digest",
            "expected_outputs",
            "resource_budget",
        },
    )
    _string(replay["command"], f"{path}.replay.command", nonempty=False)
    if _boolean(replay["display_only"], f"{path}.replay.display_only") is not True:
        raise _error(f"{path}.replay.display_only", "must be true in core v0.1")
    environment_digest = _string(
        replay["environment_digest"],
        f"{path}.replay.environment_digest",
        nonempty=False,
    )
    if environment_digest:
        _sha(environment_digest, f"{path}.replay.environment_digest")
    _strings(replay["expected_outputs"], f"{path}.replay.expected_outputs")
    _object(replay["resource_budget"], f"{path}.replay.resource_budget")


def validate_relation(record: dict[str, Any]) -> None:
    path = "relation"
    _closed(
        record,
        path,
        required={
            "issued_at",
            "issuer",
            "load_bearing",
            "protocol_version",
            "record_id",
            "record_type",
            "relation",
            "semantic_alignment",
            "source",
            "target",
        },
        optional={"extensions"},
    )
    _record_ref(record["source"], f"{path}.source")
    _record_ref(record["target"], f"{path}.target")
    _enum(record["relation"], RELATIONS, f"{path}.relation")
    _boolean(record["load_bearing"], f"{path}.load_bearing")
    _timestamp(record["issued_at"], f"{path}.issued_at")
    _issuer(record["issuer"], f"{path}.issuer")
    alignment = _object(record["semantic_alignment"], f"{path}.semantic_alignment")
    _closed(
        alignment,
        f"{path}.semantic_alignment",
        required={"definition_map", "limitations", "status"},
    )
    _enum(
        alignment["status"],
        {"checked", "contested", "partial", "unchecked"},
        f"{path}.semantic_alignment.status",
    )
    for index, mapping in enumerate(
        _array(alignment["definition_map"], f"{path}.semantic_alignment.definition_map")
    ):
        item_path = f"{path}.semantic_alignment.definition_map[{index}]"
        mapping = _object(mapping, item_path)
        _closed(
            mapping,
            item_path,
            required={"note", "source_term", "target_term"},
        )
        for field in {"note", "source_term", "target_term"}:
            _string(mapping[field], f"{item_path}.{field}", nonempty=False)
    _strings(alignment["limitations"], f"{path}.semantic_alignment.limitations")


def validate_assessment(record: dict[str, Any]) -> None:
    path = "assessment"
    _closed(
        record,
        path,
        required={
            "assessment_kind",
            "authentication",
            "dimension",
            "evidence_refs",
            "independence",
            "issued_at",
            "issuer",
            "method",
            "outcome",
            "protocol_version",
            "qualifications",
            "record_id",
            "record_type",
            "responds_to",
            "stance",
            "summary",
            "supersedes",
            "target",
            "target_claim_id",
            "withdraws",
        },
        optional={"expires_at", "extensions"},
    )
    _record_ref(record["target"], f"{path}.target")
    target_claim_id = _string(
        record["target_claim_id"],
        f"{path}.target_claim_id",
        nonempty=False,
    )
    if record["target"]["record_type"] == "claim-version":
        if not target_claim_id:
            raise _error(
                f"{path}.target_claim_id",
                "must identify the exact claim when target is a claim-version",
            )
        _ni(target_claim_id, f"{path}.target_claim_id")
    elif target_claim_id:
        raise _error(
            f"{path}.target_claim_id",
            "must be empty when target is not a claim-version",
        )
    _enum(record["assessment_kind"], ASSESSMENT_KINDS, f"{path}.assessment_kind")
    _enum(record["dimension"], DIMENSIONS, f"{path}.dimension")
    _enum(
        record["stance"],
        {"challenges", "neutral", "supports", "withdraws-prior"},
        f"{path}.stance",
    )
    _enum(
        record["outcome"],
        {"fail", "not-applicable", "pass", "unknown"},
        f"{path}.outcome",
    )
    _timestamp(record["issued_at"], f"{path}.issued_at")
    if "expires_at" in record:
        _timestamp(record["expires_at"], f"{path}.expires_at")
    _issuer(record["issuer"], f"{path}.issuer")
    _authentication(record["authentication"], f"{path}.authentication")
    _string(record["summary"], f"{path}.summary")
    _string(record["method"], f"{path}.method")
    _strings(record["qualifications"], f"{path}.qualifications")
    for field in {"evidence_refs", "responds_to", "supersedes", "withdraws"}:
        for index, ref in enumerate(_array(record[field], f"{path}.{field}")):
            _ni(ref, f"{path}.{field}[{index}]")
    if record["assessment_kind"] == "objection":
        if record["stance"] != "challenges" or record["outcome"] not in {
            "fail",
            "unknown",
        }:
            raise _error(
                path,
                "objection requires stance=challenges and outcome=fail|unknown",
            )
    if record["assessment_kind"] == "retraction":
        if record["stance"] != "challenges" or record["outcome"] != "fail":
            raise _error(
                path,
                "retraction requires stance=challenges and outcome=fail",
            )
    if record["assessment_kind"] == "withdrawal":
        if (
            record["stance"] != "withdraws-prior"
            or record["outcome"] != "not-applicable"
            or not record["withdraws"]
        ):
            raise _error(
                path,
                "withdrawal requires withdraws-prior, not-applicable, and a target",
            )
        if "expires_at" in record:
            raise _error(path, "withdrawal is a causal event and cannot expire")
    elif record["withdraws"]:
        raise _error(path, "only a withdrawal assessment may populate withdraws")
    if record["assessment_kind"] == "response" and not record["responds_to"]:
        raise _error(path, "response requires at least one responds_to reference")
    independence = _object(record["independence"], f"{path}.independence")
    _closed(
        independence,
        f"{path}.independence",
        required={
            "actor",
            "code",
            "communication_exposure",
            "coordination_parent",
            "data",
            "environment",
            "method",
            "model_provider",
            "organization",
        },
    )
    for field in independence:
        _string(independence[field], f"{path}.independence.{field}", nonempty=False)


def validate_use_receipt(record: dict[str, Any]) -> None:
    path = "use-receipt"
    _closed(
        record,
        path,
        required={
            "authentication",
            "consumer",
            "decision",
            "dimension_results",
            "evaluated_at",
            "executed_commands",
            "ignored_records",
            "inputs",
            "lineage",
            "policy",
            "policy_as_of",
            "protocol_version",
            "purpose",
            "qualifications",
            "record_id",
            "record_type",
            "retrieval",
            "subject",
            "termination",
            "unavailable_sources",
        },
        optional={"extensions"},
    )
    _timestamp(record["evaluated_at"], f"{path}.evaluated_at")
    _timestamp(record["policy_as_of"], f"{path}.policy_as_of")
    _string(record["purpose"], f"{path}.purpose")
    authentication = _object(record["authentication"], f"{path}.authentication")
    _closed(
        authentication,
        f"{path}.authentication",
        required={"accepted_record_ids", "verification_context"},
    )
    for index, ref in enumerate(
        _array(
            authentication["accepted_record_ids"],
            f"{path}.authentication.accepted_record_ids",
        )
    ):
        _ni(ref, f"{path}.authentication.accepted_record_ids[{index}]")
    _string(
        authentication["verification_context"],
        f"{path}.authentication.verification_context",
        nonempty=False,
    )
    subject = _object(record["subject"], f"{path}.subject")
    _closed(
        subject,
        f"{path}.subject",
        required={"claim_id", "claim_record_id", "package_root"},
    )
    _ni(subject["claim_id"], f"{path}.subject.claim_id")
    _ni(subject["claim_record_id"], f"{path}.subject.claim_record_id")
    _ni(subject["package_root"], f"{path}.subject.package_root")
    policy = _object(record["policy"], f"{path}.policy")
    _closed(policy, f"{path}.policy", required={"policy_id", "policy_digest"})
    _string(policy["policy_id"], f"{path}.policy.policy_id")
    _sha(policy["policy_digest"], f"{path}.policy.policy_digest")
    consumer = _object(record["consumer"], f"{path}.consumer")
    _closed(
        consumer,
        f"{path}.consumer",
        required={"name", "run_id", "version"},
        optional={"model", "role"},
    )
    for field in consumer:
        _string(consumer[field], f"{path}.consumer.{field}", nonempty=False)
    for index, item in enumerate(_array(record["inputs"], f"{path}.inputs")):
        item = _object(item, f"{path}.inputs[{index}]")
        _closed(item, f"{path}.inputs[{index}]", required={"record_id", "sha256"})
        _ni(item["record_id"], f"{path}.inputs[{index}].record_id")
        _sha(item["sha256"], f"{path}.inputs[{index}].sha256")
    input_ids = [item["record_id"] for item in record["inputs"]]
    if len(input_ids) != len(set(input_ids)):
        raise _error(f"{path}.inputs", "record IDs must be unique")
    retrieval = _object(record["retrieval"], f"{path}.retrieval")
    _closed(
        retrieval,
        f"{path}.retrieval",
        required={
            "catalogue_head",
            "objection_search_complete",
            "objection_search_context",
            "retrieved_at",
            "routes",
        },
    )
    catalogue_head = _string(
        retrieval["catalogue_head"], f"{path}.retrieval.catalogue_head", nonempty=False
    )
    if catalogue_head:
        _ni(catalogue_head, f"{path}.retrieval.catalogue_head")
        if catalogue_head == subject["package_root"]:
            raise _error(
                f"{path}.retrieval.catalogue_head",
                "must not relabel the subject package root as a catalogue head",
            )
    _timestamp(retrieval["retrieved_at"], f"{path}.retrieval.retrieved_at")
    _strings(retrieval["routes"], f"{path}.retrieval.routes")
    _boolean(
        retrieval["objection_search_complete"],
        f"{path}.retrieval.objection_search_complete",
    )
    _string(
        retrieval["objection_search_context"],
        f"{path}.retrieval.objection_search_context",
        nonempty=False,
    )
    try:
        policy_as_of = datetime.fromisoformat(
            record["policy_as_of"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        evaluated_at = datetime.fromisoformat(
            record["evaluated_at"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        retrieved_at = datetime.fromisoformat(
            retrieval["retrieved_at"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise _error(path, "receipt timestamps cannot be normalized to UTC") from exc
    if policy_as_of > evaluated_at or policy_as_of > retrieved_at:
        raise _error(
            f"{path}.policy_as_of",
            "must not be later than actual evaluation or retrieval time",
        )
    results = _object(record["dimension_results"], f"{path}.dimension_results")
    if set(results) - DIMENSIONS:
        raise _error(f"{path}.dimension_results", "contains an unknown dimension")
    for dimension, result in results.items():
        item_path = f"{path}.dimension_results.{dimension}"
        result = _object(result, item_path)
        _closed(
            result,
            item_path,
            required={"result", "basis", "assessment_refs"},
        )
        _enum(result["result"], {"fail", "pass", "unknown"}, f"{item_path}.result")
        _strings(result["basis"], f"{item_path}.basis")
        for index, ref in enumerate(
            _array(result["assessment_refs"], f"{item_path}.assessment_refs")
        ):
            _ni(ref, f"{item_path}.assessment_refs[{index}]")
    _enum(record["decision"], {"ALLOW", "DENY", "UNKNOWN"}, f"{path}.decision")
    result_values = [item["result"] for item in results.values()]
    if not result_values:
        raise _error(f"{path}.dimension_results", "must not be empty")
    if record["decision"] == "ALLOW" and any(
        result != "pass" for result in result_values
    ):
        raise _error(path, "ALLOW requires every dimension result to pass")
    if record["decision"] == "DENY" and "fail" not in result_values:
        raise _error(path, "DENY requires at least one failed dimension")
    for field in {"qualifications", "unavailable_sources", "executed_commands"}:
        _strings(record[field], f"{path}.{field}")
    if record["executed_commands"]:
        raise _error(f"{path}.executed_commands", "must be empty in core safe mode")
    for field in {"ignored_records"}:
        for index, ref in enumerate(_array(record[field], f"{path}.{field}")):
            _ni(ref, f"{path}.{field}[{index}]")
    termination = _object(record["termination"], f"{path}.termination")
    _closed(termination, f"{path}.termination", required={"reason", "limits_hit"})
    _enum(
        termination["reason"],
        {"completed", "cycle", "error", "limit", "missing-input", "stale-input"},
        f"{path}.termination.reason",
    )
    _strings(termination["limits_hit"], f"{path}.termination.limits_hit")
    if record["decision"] == "ALLOW" and (
        termination["reason"] != "completed" or termination["limits_hit"]
    ):
        raise _error(path, "ALLOW requires completed termination without limits")
    if record["decision"] == "UNKNOWN" and not (
        "unknown" in result_values
        or termination["reason"]
        in {"cycle", "error", "limit", "missing-input", "stale-input"}
    ):
        raise _error(
            path,
            "UNKNOWN requires an unknown dimension or incomplete termination",
        )
    lineage = _object(record["lineage"], f"{path}.lineage")
    _closed(lineage, f"{path}.lineage", required={"parent_receipt_id", "source_run_id"})
    parent = _string(
        lineage["parent_receipt_id"],
        f"{path}.lineage.parent_receipt_id",
        nonempty=False,
    )
    if parent:
        _ni(parent, f"{path}.lineage.parent_receipt_id")
    _string(lineage["source_run_id"], f"{path}.lineage.source_run_id", nonempty=False)
    accepted_ids = authentication["accepted_record_ids"]
    if set(accepted_ids) - set(input_ids):
        raise _error(
            f"{path}.authentication.accepted_record_ids",
            "authenticated records must be pinned inputs",
        )
    assessment_refs = {
        ref for result in results.values() for ref in result["assessment_refs"]
    }
    if assessment_refs - set(input_ids):
        raise _error(
            f"{path}.dimension_results",
            "assessment references must be pinned inputs",
        )


def validate_record(record: dict[str, Any]) -> None:
    _object(record, "record")
    if record.get("protocol_version") != PROTOCOL_VERSION:
        raise _error("record.protocol_version", f"must equal {PROTOCOL_VERSION!r}")
    record_type = _enum(record.get("record_type"), RECORD_TYPES, "record.record_type")
    _ni(record.get("record_id"), "record.record_id")
    validators = {
        "assessment": validate_assessment,
        "claim-version": validate_claim_version,
        "evidence": validate_evidence,
        "relation": validate_relation,
        "use-receipt": validate_use_receipt,
    }
    validators[record_type](record)
    expected = record_id_for(record)
    if record["record_id"] != expected:
        raise _error("record.record_id", f"identity mismatch; expected {expected}")


def validate_manifest(manifest: dict[str, Any]) -> None:
    path = "manifest"
    _closed(
        manifest,
        path,
        required={
            "artifacts",
            "created_at",
            "package_root",
            "records",
            "schema_version",
        },
        optional={"extensions"},
    )
    if manifest["schema_version"] != MANIFEST_VERSION:
        raise _error(path, f"unsupported schema_version {manifest['schema_version']!r}")
    _timestamp(manifest["created_at"], f"{path}.created_at")
    _ni(manifest["package_root"], f"{path}.package_root")
    seen_paths: set[str] = set()
    seen_ids: set[str] = set()
    for index, item in enumerate(_array(manifest["records"], f"{path}.records")):
        item_path = f"{path}.records[{index}]"
        item = _object(item, item_path)
        _closed(
            item,
            item_path,
            required={"media_type", "path", "record_id", "record_type", "sha256"},
        )
        package_path = validate_relative_path(
            _string(item["path"], f"{item_path}.path")
        )
        if package_path in seen_paths:
            raise _error(f"{item_path}.path", "duplicate manifest path")
        seen_paths.add(package_path)
        record_id = _ni(item["record_id"], f"{item_path}.record_id")
        if record_id in seen_ids:
            raise _error(f"{item_path}.record_id", "duplicate record ID")
        seen_ids.add(record_id)
        _enum(item["record_type"], RECORD_TYPES, f"{item_path}.record_type")
        _sha(item["sha256"], f"{item_path}.sha256")
        if item["media_type"] != "application/json":
            raise _error(f"{item_path}.media_type", "must equal application/json")
    for index, item in enumerate(_array(manifest["artifacts"], f"{path}.artifacts")):
        item_path = f"{path}.artifacts[{index}]"
        item = _object(item, item_path)
        _closed(item, item_path, required={"media_type", "path", "sha256"})
        package_path = validate_relative_path(
            _string(item["path"], f"{item_path}.path")
        )
        if package_path in seen_paths:
            raise _error(f"{item_path}.path", "duplicate manifest path")
        seen_paths.add(package_path)
        _sha(item["sha256"], f"{item_path}.sha256")
        _string(item["media_type"], f"{item_path}.media_type")
    if "extensions" in manifest:
        extensions = _object(manifest["extensions"], f"{path}.extensions")
        if "primary_claim_record_id" in extensions:
            _ni(
                extensions["primary_claim_record_id"],
                f"{path}.extensions.primary_claim_record_id",
            )
    expected = package_root_for(manifest)
    if manifest["package_root"] != expected:
        raise _error(
            f"{path}.package_root",
            f"identity mismatch; expected {expected}",
        )


def validate_policy(policy: dict[str, Any]) -> None:
    path = "policy"
    _closed(
        policy,
        path,
        required={
            "adverse_issuers",
            "dimensions",
            "limits",
            "max_assessment_age_days",
            "open_objection_effect",
            "policy_digest",
            "policy_id",
            "policy_version",
            "require_authenticated_positive",
            "require_complete_objection_search",
            "require_evidence_for_positive",
            "require_embedded_evidence_for_positive",
        },
    )
    _string(policy["policy_id"], f"{path}.policy_id")
    _string(policy["policy_version"], f"{path}.policy_version")
    _sha(policy["policy_digest"], f"{path}.policy_digest")
    dimensions = _object(policy["dimensions"], f"{path}.dimensions")
    if not dimensions:
        raise _error(f"{path}.dimensions", "must require at least one dimension")
    for dimension, rule in dimensions.items():
        if dimension not in DIMENSIONS:
            raise _error(f"{path}.dimensions", f"unknown dimension {dimension!r}")
        item_path = f"{path}.dimensions.{dimension}"
        rule = _object(rule, item_path)
        _closed(
            rule,
            item_path,
            required={"accepted_issuers", "required"},
        )
        _boolean(rule["required"], f"{item_path}.required")
        _strings(rule["accepted_issuers"], f"{item_path}.accepted_issuers")
    if not any(rule["required"] for rule in dimensions.values()):
        raise _error(f"{path}.dimensions", "must require at least one dimension")
    _strings(policy["adverse_issuers"], f"{path}.adverse_issuers")
    limits = _object(policy["limits"], f"{path}.limits")
    _closed(
        limits,
        f"{path}.limits",
        required={"assessment_count", "dependency_depth", "dependency_nodes"},
    )
    for field in limits:
        raw = _string(limits[field], f"{path}.limits.{field}")
        try:
            parsed = int(raw)
        except ValueError as exc:
            raise _error(
                f"{path}.limits.{field}",
                "must be a decimal integer string",
            ) from exc
        if parsed < 1:
            raise _error(f"{path}.limits.{field}", "must be positive")
        upper_bounds = {
            "assessment_count": 10_000,
            "dependency_depth": 256,
            "dependency_nodes": 10_000,
        }
        if parsed > upper_bounds[field]:
            raise _error(
                f"{path}.limits.{field}",
                f"must not exceed {upper_bounds[field]}",
            )
    _string(policy["max_assessment_age_days"], f"{path}.max_assessment_age_days")
    try:
        days = int(policy["max_assessment_age_days"])
    except ValueError as exc:
        raise _error(
            f"{path}.max_assessment_age_days", "must be a decimal integer string"
        ) from exc
    if days < 0:
        raise _error(f"{path}.max_assessment_age_days", "must be non-negative")
    if days > 365_000:
        raise _error(
            f"{path}.max_assessment_age_days",
            "must not exceed 365000",
        )
    _enum(
        policy["open_objection_effect"],
        {"deny", "unknown"},
        f"{path}.open_objection_effect",
    )
    _boolean(
        policy["require_authenticated_positive"],
        f"{path}.require_authenticated_positive",
    )
    _boolean(
        policy["require_complete_objection_search"],
        f"{path}.require_complete_objection_search",
    )
    require_evidence = _boolean(
        policy["require_evidence_for_positive"],
        f"{path}.require_evidence_for_positive",
    )
    require_embedded = _boolean(
        policy["require_embedded_evidence_for_positive"],
        f"{path}.require_embedded_evidence_for_positive",
    )
    if require_embedded and not require_evidence:
        raise _error(
            path,
            "embedded positive evidence cannot be required when evidence is optional",
        )
    expected = policy_digest_for(policy)
    if policy["policy_digest"] != expected:
        raise _error(
            f"{path}.policy_digest",
            f"identity mismatch; expected {expected}",
        )

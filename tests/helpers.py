from __future__ import annotations

from pathlib import Path
from typing import Any

from claimpack.build import seal_record, write_pack
from claimpack.ids import policy_digest_for, sha256_label

NOW = "2026-07-29T12:00:00+00:00"
REVIEWER = "reviewer:test"


def make_claim(
    *,
    natural: str = "For every test object x, property P(x) holds.",
    aliases: list[str] | None = None,
    lineage: list[dict[str, str]] | None = None,
    dependency_targets: list[dict[str, str]] | None = None,
    conditions: list[str] | None = None,
) -> dict[str, Any]:
    return seal_record(
        {
            "aliases": aliases or ["test theorem"],
            "claim_version": "test-v1",
            "dependency_targets": dependency_targets or [],
            "formal_statements": [],
            "issued_at": NOW,
            "lineage": lineage or [],
            "problem_refs": [{"id": "T-1", "scheme": "test"}],
            "protocol_version": "0.1.0",
            "provenance": {
                "actors": [
                    {
                        "display_name": "Test producer",
                        "id": "producer:test",
                        "kind": "organization",
                    }
                ],
                "roles": [
                    {
                        "actor_id": "producer:test",
                        "date": NOW,
                        "role": "fixture production",
                    }
                ],
            },
            "record_type": "claim-version",
            "rights": {
                "exclusions": [],
                "license": "CC0-1.0",
                "scope": "Synthetic test record.",
            },
            "scope": {
                "claim_kind": "full-result",
                "conditions": conditions or ["retain root condition"],
                "exclusions": ["retain root exclusion"],
                "non_implications": ["retain root non-implication"],
                "scope_note": "Synthetic fixture.",
                "structured_scope": {"domain": "test"},
                "targets": ["test target"],
            },
            "sources": [
                {
                    "immutable": True,
                    "kind": "other",
                    "locator": "urn:claimpack:test",
                    "rights": "CC0-1.0",
                    "version": "1",
                }
            ],
            "statement": {
                "definitions": [{"meaning": "A test predicate.", "term": "P"}],
                "language": "en",
                "latex": r"\forall x,\ P(x)",
                "natural": natural,
                "quantifiers": ["for every test object x"],
            },
        }
    )


def make_evidence(
    claim: dict[str, Any],
    data: bytes,
    *,
    embedded: bool = True,
    path: str = "artifacts/evidence.txt",
) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "digest": sha256_label(data),
        "embedded": embedded,
        "media_type": "text/plain",
        "name": "synthetic evidence",
        "rights": "CC0-1.0",
    }
    if embedded:
        artifact["path"] = path
    else:
        artifact["locator"] = "https://invalid.example/evidence.txt"
    return seal_record(
        {
            "artifacts": [artifact],
            "coverage": ["synthetic statement and objection-search fixture"],
            "evidence_kind": "review-material",
            "issued_at": NOW,
            "issuer": {
                "display_name": "Test reviewer",
                "id": REVIEWER,
                "kind": "organization",
            },
            "limitations": ["retain evidence limitation"],
            "method": "Synthetic deterministic fixture.",
            "protocol_version": "0.1.0",
            "record_type": "evidence",
            "replay": {
                "command": "DO NOT EXECUTE package text",
                "display_only": True,
                "environment_digest": "",
                "expected_outputs": ["none; fixture only"],
                "resource_budget": {"wall_time": "zero"},
            },
            "subject": {
                "record_id": claim["record_id"],
                "record_type": claim["record_type"],
            },
        }
    )


def make_assessment(
    target: dict[str, Any],
    *,
    dimension: str,
    outcome: str = "pass",
    stance: str | None = None,
    assessment_kind: str = "review",
    issuer_id: str = REVIEWER,
    issued_at: str = NOW,
    evidence_refs: list[str] | None = None,
    qualifications: list[str] | None = None,
    authentication: str = "claimed-verified",
    withdraws: list[str] | None = None,
    responds_to: list[str] | None = None,
) -> dict[str, Any]:
    if stance is None:
        stance = "supports" if outcome == "pass" else "neutral"
    return seal_record(
        {
            "assessment_kind": assessment_kind,
            "authentication": {"status": authentication},
            "dimension": dimension,
            "evidence_refs": evidence_refs or [],
            "independence": {
                "actor": "independent test actor",
                "code": "independent synthetic path",
                "communication_exposure": "none",
                "coordination_parent": "none",
                "data": "fixture data",
                "environment": "test environment",
                "method": "synthetic test method",
                "model_provider": "",
                "organization": "test organization",
            },
            "issued_at": issued_at,
            "issuer": {
                "display_name": issuer_id,
                "id": issuer_id,
                "kind": "organization",
            },
            "method": "Synthetic review fixture.",
            "outcome": outcome,
            "protocol_version": "0.1.0",
            "qualifications": qualifications or ["retain assessment qualification"],
            "record_type": "assessment",
            "responds_to": responds_to or [],
            "stance": stance,
            "summary": f"Synthetic {dimension} assessment.",
            "supersedes": [],
            "target": {
                "record_id": target["record_id"],
                "record_type": target["record_type"],
            },
            "target_claim_id": (
                target["claim_id"] if target["record_type"] == "claim-version" else ""
            ),
            "withdraws": withdraws or [],
        }
    )


def make_objection(
    target: dict[str, Any],
    *,
    issuer_id: str = "objector:test",
    issued_at: str = NOW,
) -> dict[str, Any]:
    return make_assessment(
        target,
        dimension="proof-completeness",
        outcome="unknown",
        stance="challenges",
        assessment_kind="objection",
        issuer_id=issuer_id,
        issued_at=issued_at,
        evidence_refs=[],
        qualifications=["retain objection qualification"],
        authentication="unverified",
    )


def make_withdrawal(
    target: dict[str, Any],
    objection: dict[str, Any],
    *,
    issued_at: str = "2026-07-29T13:00:00+00:00",
) -> dict[str, Any]:
    return make_assessment(
        target,
        dimension=objection["dimension"],
        outcome="not-applicable",
        stance="withdraws-prior",
        assessment_kind="withdrawal",
        issuer_id=objection["issuer"]["id"],
        issued_at=issued_at,
        evidence_refs=[],
        qualifications=["objection withdrawn by its issuer"],
        authentication="claimed-verified",
        withdraws=[objection["record_id"]],
    )


def make_policy(
    *,
    open_objection_effect: str = "unknown",
    max_age_days: str = "30",
    assessment_count: str = "64",
) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "adverse_issuers": ["*"],
        "dimensions": {
            "dependency-closure": {
                "accepted_issuers": [REVIEWER],
                "required": True,
            },
            "known-objections": {
                "accepted_issuers": [REVIEWER],
                "required": True,
            },
            "statement-precision": {
                "accepted_issuers": [REVIEWER],
                "required": True,
            },
        },
        "limits": {
            "assessment_count": assessment_count,
            "dependency_depth": "8",
            "dependency_nodes": "32",
        },
        "max_assessment_age_days": max_age_days,
        "open_objection_effect": open_objection_effect,
        "policy_digest": "",
        "policy_id": "claimpack:test-policy",
        "policy_version": "1",
        "require_authenticated_positive": True,
        "require_complete_objection_search": True,
        "require_embedded_evidence_for_positive": True,
        "require_evidence_for_positive": True,
    }
    policy["policy_digest"] = policy_digest_for(policy)
    return policy


def demo_components(
    *,
    data: bytes = b"synthetic evidence\n",
    natural: str = "For every test object x, property P(x) holds.",
    assessment_time: str = NOW,
    embedded: bool = True,
    aliases: list[str] | None = None,
    lineage: list[dict[str, str]] | None = None,
    dependency_targets: list[dict[str, str]] | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, tuple[bytes, str]],
]:
    claim = make_claim(
        natural=natural,
        aliases=aliases,
        lineage=lineage,
        dependency_targets=dependency_targets,
    )
    evidence = make_evidence(claim, data, embedded=embedded)
    assessments = [
        make_assessment(
            claim,
            dimension=dimension,
            issued_at=assessment_time,
            evidence_refs=[evidence["record_id"]],
        )
        for dimension in [
            "dependency-closure",
            "known-objections",
            "statement-precision",
        ]
    ]
    artifacts = {"artifacts/evidence.txt": (data, "text/plain")} if embedded else {}
    return claim, evidence, assessments, artifacts


def make_relation(
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    status: str = "checked",
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return seal_record(
        {
            "issued_at": NOW,
            "issuer": {
                "display_name": "Test reviewer",
                "id": REVIEWER,
                "kind": "organization",
            },
            "load_bearing": True,
            "protocol_version": "0.1.0",
            "record_type": "relation",
            "relation": "depends-on",
            "semantic_alignment": {
                "definition_map": [
                    {
                        "note": "synthetic exact map",
                        "source_term": "P",
                        "target_term": "P",
                    }
                ],
                "limitations": limitations or ["retain relation limitation"],
                "status": status,
            },
            "source": {
                "record_id": source["record_id"],
                "record_type": "claim-version",
            },
            "target": {
                "record_id": target["record_id"],
                "record_type": "claim-version",
            },
        }
    )


def write_demo(
    destination: Path,
    *,
    claim: dict[str, Any],
    evidence: dict[str, Any],
    assessments: list[dict[str, Any]],
    artifacts: dict[str, tuple[bytes, str]],
    extra_records: list[dict[str, Any]] | None = None,
) -> Path:
    return write_pack(
        destination,
        records=[claim, evidence] + assessments + (extra_records or []),
        artifacts=artifacts,
        created_at=NOW,
        primary_claim_record_id=claim["record_id"],
    )

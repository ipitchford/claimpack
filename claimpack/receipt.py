"""Qualification-preserving UseReceipt creation and verification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .canonical import canonical_bytes
from .ids import record_id_for, sha256_label
from .policy import PolicyEvaluation
from .records import validate_record
from .validate import ValidatedPack


def create_use_receipt(
    pack: ValidatedPack,
    claim: dict[str, Any],
    policy: dict[str, Any],
    evaluation: PolicyEvaluation,
    *,
    purpose: str,
    consumer_name: str = "claimpack",
    consumer_version: str = "0.1.0.dev0",
    consumer_run_id: str = "",
    consumer_model: str = "",
    consumer_role: str = "research-claim consumer",
    routes: list[str] | None = None,
    catalogue_head: str = "",
    retrieved_at: str | None = None,
    parent_receipt_id: str = "",
    source_run_id: str = "",
) -> dict[str, Any]:
    if claim["record_id"] not in pack.records:
        raise ValueError("receipt claim is not embedded in the evaluated package")
    if (
        evaluation.package_root != pack.package_root
        or evaluation.claim_record_id != claim["record_id"]
        or evaluation.claim_id != claim["claim_id"]
    ):
        raise ValueError("receipt subject does not match the policy evaluation")
    if (
        evaluation.policy_id != policy["policy_id"]
        or evaluation.policy_digest != policy["policy_digest"]
    ):
        raise ValueError("receipt policy does not match the policy evaluation")
    if catalogue_head and catalogue_head == pack.package_root:
        raise ValueError("package root cannot be relabelled as a catalogue head")
    evaluated_at = evaluation.evaluated_at
    if retrieved_at is None:
        retrieved_at = datetime.now(timezone.utc).isoformat()
    manifest_by_id = {entry["record_id"]: entry for entry in pack.manifest["records"]}
    inputs: list[dict[str, str]] = []
    for record in evaluation.used_records:
        entry = manifest_by_id.get(record["record_id"])
        digest = (
            entry["sha256"]
            if entry is not None
            else sha256_label(canonical_bytes(record))
        )
        inputs.append({"record_id": record["record_id"], "sha256": digest})

    receipt: dict[str, Any] = {
        "authentication": {
            "accepted_record_ids": list(evaluation.authenticated_record_ids),
            "verification_context": evaluation.authentication_context,
        },
        "consumer": {
            "model": consumer_model,
            "name": consumer_name,
            "role": consumer_role,
            "run_id": consumer_run_id,
            "version": consumer_version,
        },
        "decision": evaluation.decision.value,
        "dimension_results": {
            key: value.as_dict()
            for key, value in sorted(evaluation.dimension_results.items())
        },
        "evaluated_at": evaluated_at,
        "executed_commands": [],
        "ignored_records": list(evaluation.ignored_records),
        "inputs": sorted(inputs, key=lambda item: item["record_id"]),
        "lineage": {
            "parent_receipt_id": parent_receipt_id,
            "source_run_id": source_run_id,
        },
        "policy": {
            "policy_digest": policy["policy_digest"],
            "policy_id": policy["policy_id"],
        },
        "policy_as_of": evaluation.policy_as_of,
        "protocol_version": "0.1.0",
        "purpose": purpose,
        "qualifications": list(evaluation.qualifications),
        "record_id": "",
        "record_type": "use-receipt",
        "retrieval": {
            "catalogue_head": catalogue_head,
            "objection_search_complete": evaluation.objection_search_complete,
            "objection_search_context": evaluation.objection_search_context,
            "retrieved_at": retrieved_at,
            "routes": routes or [f"local:{pack.source}"],
        },
        "subject": {
            "claim_id": claim["claim_id"],
            "claim_record_id": claim["record_id"],
            "package_root": pack.package_root,
        },
        "termination": {
            "limits_hit": list(evaluation.limits_hit),
            "reason": evaluation.termination_reason,
        },
        "unavailable_sources": list(evaluation.unavailable_sources),
    }
    receipt["record_id"] = record_id_for(receipt)
    validate_record(receipt)
    return receipt


def verify_use_receipt(receipt: dict[str, Any]) -> None:
    """Validate receipt structure and identity, not the underlying decision."""

    validate_record(receipt)
    if receipt["record_type"] != "use-receipt":
        raise ValueError("record is not a UseReceipt")

"""Offline comparison of immutable static-catalogue snapshots."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .canonical import canonical_bytes
from .errors import ValidationError
from .ids import ni_sha256
from .reader import validate_relative_path

CATALOG_VERSION = "claimpack-static-catalog/0.1"
NI_RE = re.compile(r"^ni:///sha-256;[A-Za-z0-9_-]{43}$")
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ENTRY_FIELDS = {
    "aliases",
    "assessment_record_ids",
    "author_claimed_status",
    "canonical_status",
    "claim_id",
    "claim_kind",
    "claim_record_id",
    "formal_verification_status",
    "human_review_status",
    "independent_reproduction_status",
    "latex",
    "natural",
    "novelty_status",
    "objection_record_ids",
    "packages",
    "search_fingerprint",
    "sources",
    "status_updated_at",
    "system_assessment",
}


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise ValidationError(f"{path} must be a string")
    return value


def _ni(value: Any, path: str) -> str:
    value = _string(value, path)
    if not NI_RE.fullmatch(value):
        raise ValidationError(f"{path} must be a SHA-256 ni URI")
    return value


def _sha(value: Any, path: str) -> str:
    value = _string(value, path)
    if not SHA_RE.fullmatch(value):
        raise ValidationError(f"{path} must be a sha256 digest")
    return value


def _timestamp(value: Any, path: str) -> str:
    value = _string(value, path)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("missing timezone")
        parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    return value


def _string_list(value: Any, path: str, *, identifiers: bool = False) -> None:
    if not isinstance(value, list):
        raise ValidationError(f"{path} must be an array")
    for index, item in enumerate(value):
        if identifiers:
            _ni(item, f"{path}[{index}]")
        else:
            _string(item, f"{path}[{index}]")
    if len(value) != len(set(value)):
        raise ValidationError(f"{path} must not contain duplicates")


def validate_catalog(catalog: dict[str, Any]) -> None:
    if not isinstance(catalog, dict):
        raise ValidationError("catalog must be an object")
    if set(catalog) != {
        "catalog_head",
        "entries",
        "generated_at",
        "schema_version",
        "search_fingerprint_profile",
    }:
        raise ValidationError("catalog has missing or unknown top-level fields")
    if catalog["schema_version"] != CATALOG_VERSION:
        raise ValidationError("unsupported catalog version")
    _ni(catalog["catalog_head"], "catalog.catalog_head")
    _timestamp(catalog["generated_at"], "catalog.generated_at")
    _string(
        catalog["search_fingerprint_profile"],
        "catalog.search_fingerprint_profile",
    )
    if not isinstance(catalog["entries"], list):
        raise ValidationError("catalog entries must be an array")
    seen: set[str] = set()
    for index, entry in enumerate(catalog["entries"]):
        path = f"catalog.entries[{index}]"
        if not isinstance(entry, dict):
            raise ValidationError(f"catalog entry {index} must be an object")
        if set(entry) != ENTRY_FIELDS:
            raise ValidationError(f"{path} has missing or unknown fields")
        record_id = _ni(entry["claim_record_id"], f"{path}.claim_record_id")
        _ni(entry["claim_id"], f"{path}.claim_id")
        if record_id in seen:
            raise ValidationError(f"duplicate catalog claim_record_id: {record_id}")
        seen.add(record_id)
        for field in {
            "author_claimed_status",
            "canonical_status",
            "claim_kind",
            "formal_verification_status",
            "human_review_status",
            "independent_reproduction_status",
            "natural",
            "novelty_status",
            "system_assessment",
        }:
            _string(entry[field], f"{path}.{field}")
        _string(entry["latex"], f"{path}.latex", nonempty=False)
        _sha(entry["search_fingerprint"], f"{path}.search_fingerprint")
        _timestamp(entry["status_updated_at"], f"{path}.status_updated_at")
        _string_list(entry["aliases"], f"{path}.aliases")
        _string_list(
            entry["assessment_record_ids"],
            f"{path}.assessment_record_ids",
            identifiers=True,
        )
        _string_list(
            entry["objection_record_ids"],
            f"{path}.objection_record_ids",
            identifiers=True,
        )
        if not isinstance(entry["packages"], list):
            raise ValidationError(f"catalog entry {index} packages must be an array")
        for package_index, package in enumerate(entry["packages"]):
            package_path = f"{path}.packages[{package_index}]"
            if not isinstance(package, dict) or set(package) != {
                "package_root",
                "path",
                "primary",
            }:
                raise ValidationError(f"{package_path} has invalid fields")
            _ni(package["package_root"], f"{package_path}.package_root")
            validate_relative_path(_string(package["path"], f"{package_path}.path"))
            if not isinstance(package["primary"], bool):
                raise ValidationError(f"{package_path}.primary must be a boolean")
        if not isinstance(entry["sources"], list):
            raise ValidationError(f"{path}.sources must be an array")
        for source_index, source in enumerate(entry["sources"]):
            source_path = f"{path}.sources[{source_index}]"
            if not isinstance(source, dict):
                raise ValidationError(f"{source_path} must be an object")
            required = {"immutable", "kind", "locator"}
            optional = {"digest", "retrieved_at", "rights", "version"}
            if required - source.keys() or source.keys() - required - optional:
                raise ValidationError(f"{source_path} has invalid fields")
            if not isinstance(source["immutable"], bool):
                raise ValidationError(f"{source_path}.immutable must be a boolean")
            _string(source["kind"], f"{source_path}.kind")
            _string(source["locator"], f"{source_path}.locator")
            if "digest" in source:
                _sha(source["digest"], f"{source_path}.digest")
            if "retrieved_at" in source:
                _timestamp(source["retrieved_at"], f"{source_path}.retrieved_at")
            for field in {"rights", "version"}:
                if field in source:
                    _string(source[field], f"{source_path}.{field}")
    projection = dict(catalog)
    projection.pop("catalog_head")
    expected = ni_sha256(canonical_bytes(projection))
    if catalog["catalog_head"] != expected:
        raise ValidationError(f"catalog identity mismatch; expected {expected}")


def diff_catalogs(
    older: dict[str, Any],
    newer: dict[str, Any],
) -> dict[str, Any]:
    """Return non-authoritative change events; disappearance is not retraction."""

    validate_catalog(older)
    validate_catalog(newer)
    old_entries = {item["claim_record_id"]: item for item in older["entries"]}
    new_entries = {item["claim_record_id"]: item for item in newer["entries"]}
    events: list[dict[str, Any]] = []

    for record_id in sorted(new_entries.keys() - old_entries.keys()):
        events.append(
            {
                "claim_id": new_entries[record_id]["claim_id"],
                "claim_record_id": record_id,
                "event": "claim-record-added",
                "meaning": "Present in newer snapshot; no correctness inference.",
            }
        )
    for record_id in sorted(old_entries.keys() - new_entries.keys()):
        events.append(
            {
                "claim_id": old_entries[record_id]["claim_id"],
                "claim_record_id": record_id,
                "event": "claim-record-disappeared",
                "meaning": (
                    "Absent from newer snapshot; retain prior adverse state and "
                    "do not infer withdrawal or retraction."
                ),
            }
        )
    for record_id in sorted(old_entries.keys() & new_entries.keys()):
        old_packages = old_entries[record_id]["packages"]
        new_packages = new_entries[record_id]["packages"]
        if old_packages != new_packages:
            events.append(
                {
                    "claim_id": new_entries[record_id]["claim_id"],
                    "claim_record_id": record_id,
                    "event": "package-binding-changed",
                    "meaning": "Compare exact package roots before use.",
                }
            )

    return {
        "events": events,
        "new_catalog_head": newer["catalog_head"],
        "old_catalog_head": older["catalog_head"],
        "schema_version": "claimpack-catalog-diff/0.1",
    }

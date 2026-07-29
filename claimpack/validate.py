"""Read-only package integrity and record validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import strict_loads
from .errors import ValidationError
from .ids import sha256_label
from .reader import PackReader
from .records import validate_manifest, validate_record

MANIFEST_PATH = "claimpack.json"


@dataclass(frozen=True)
class ValidatedPack:
    source: str
    manifest: dict[str, Any]
    records: dict[str, dict[str, Any]]
    record_paths: dict[str, str]
    warnings: tuple[str, ...] = ()

    @property
    def package_root(self) -> str:
        return self.manifest["package_root"]

    def claims(self) -> list[dict[str, Any]]:
        return [
            record
            for record in self.records.values()
            if record["record_type"] == "claim-version"
        ]

    def primary_claim(self) -> dict[str, Any] | None:
        record_id = self.manifest.get("extensions", {}).get("primary_claim_record_id")
        return self.records.get(record_id) if record_id else None


def validate_pack(source: str) -> ValidatedPack:
    """Validate exact inventory, hashes, schemas, and content identifiers."""

    with PackReader(source) as reader:
        inventory = set(reader.list_files())
        if MANIFEST_PATH not in inventory:
            raise ValidationError(f"missing {MANIFEST_PATH}")
        manifest = strict_loads(reader.read_bytes(MANIFEST_PATH))
        if not isinstance(manifest, dict):
            raise ValidationError("manifest must be a JSON object")
        validate_manifest(manifest)

        declared = {MANIFEST_PATH}
        records: dict[str, dict[str, Any]] = {}
        record_paths: dict[str, str] = {}

        for entry in manifest["records"]:
            path = entry["path"]
            declared.add(path)
            data = reader.read_bytes(path)
            actual_digest = sha256_label(data)
            if actual_digest != entry["sha256"]:
                raise ValidationError(
                    f"{path}: digest mismatch; expected {entry['sha256']}, "
                    f"found {actual_digest}"
                )
            record = strict_loads(data)
            if not isinstance(record, dict):
                raise ValidationError(f"{path}: record must be a JSON object")
            validate_record(record)
            if record["record_type"] != entry["record_type"]:
                raise ValidationError(f"{path}: manifest record_type mismatch")
            if record["record_id"] != entry["record_id"]:
                raise ValidationError(f"{path}: manifest record_id mismatch")
            records[record["record_id"]] = record
            record_paths[record["record_id"]] = path

        for entry in manifest["artifacts"]:
            path = entry["path"]
            declared.add(path)
            data = reader.read_bytes(path)
            actual_digest = sha256_label(data)
            if actual_digest != entry["sha256"]:
                raise ValidationError(
                    f"{path}: digest mismatch; expected {entry['sha256']}, "
                    f"found {actual_digest}"
                )

        missing = declared - inventory
        extra = inventory - declared
        if missing:
            raise ValidationError(
                f"manifest references missing paths: {sorted(missing)}"
            )
        if extra:
            raise ValidationError(f"package contains undeclared paths: {sorted(extra)}")

        _validate_evidence_artifacts(records, manifest)
        _validate_cross_references(records)
        primary = manifest.get("extensions", {}).get("primary_claim_record_id")
        if primary is not None:
            if primary not in records:
                raise ValidationError(
                    "manifest primary_claim_record_id is not embedded"
                )
            if records[primary]["record_type"] != "claim-version":
                raise ValidationError(
                    "manifest primary_claim_record_id is not a ClaimVersion"
                )

    return ValidatedPack(
        source=str(source),
        manifest=manifest,
        records=records,
        record_paths=record_paths,
    )


def _validate_cross_references(records: dict[str, dict[str, Any]]) -> None:
    """Validate embedded references without requiring remote dependencies."""

    for record in records.values():
        record_type = record["record_type"]
        if record_type in {"assessment", "evidence"}:
            target = (
                record["target"] if record_type == "assessment" else record["subject"]
            )
            target_record = records.get(target["record_id"])
            if (
                target_record is not None
                and target_record["record_type"] != target["record_type"]
            ):
                raise ValidationError(
                    f"{record['record_id']}: target record_type does not match embedded record"
                )
            if (
                record_type == "assessment"
                and target_record is not None
                and target_record["record_type"] == "claim-version"
                and record["target_claim_id"] != target_record["claim_id"]
            ):
                raise ValidationError(
                    f"{record['record_id']}: target_claim_id does not match "
                    "embedded ClaimVersion"
                )
        if record_type == "assessment":
            for ref in record["evidence_refs"]:
                if ref in records and records[ref]["record_type"] != "evidence":
                    raise ValidationError(
                        f"{record['record_id']}: evidence_refs type mismatch"
                    )
            for field in {"responds_to", "supersedes", "withdraws"}:
                for ref in record[field]:
                    if ref in records and records[ref]["record_type"] != "assessment":
                        raise ValidationError(
                            f"{record['record_id']}: {field} type mismatch"
                        )
        if record_type == "relation":
            for endpoint_name in {"source", "target"}:
                endpoint = record[endpoint_name]
                target_record = records.get(endpoint["record_id"])
                if (
                    target_record is not None
                    and target_record["record_type"] != endpoint["record_type"]
                ):
                    raise ValidationError(
                        f"{record['record_id']}: {endpoint_name} record_type mismatch"
                    )
        if record_type == "claim-version":
            for target in record["dependency_targets"]:
                embedded = records.get(target["record_id"])
                if embedded is not None and embedded["record_type"] != "claim-version":
                    raise ValidationError(
                        f"{record['record_id']}: dependency target type mismatch"
                    )
            for predecessor in record["lineage"]:
                embedded = records.get(predecessor["record_id"])
                if embedded is not None and embedded["record_type"] != "claim-version":
                    raise ValidationError(
                        f"{record['record_id']}: lineage predecessor type mismatch"
                    )


def _validate_evidence_artifacts(
    records: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    """Bind every embedded Evidence artifact to the exact manifest bytes."""

    manifest_artifacts = {entry["path"]: entry for entry in manifest["artifacts"]}
    referenced_paths: set[str] = set()
    for record in records.values():
        if record["record_type"] != "evidence":
            continue
        for artifact in record["artifacts"]:
            if not artifact["embedded"]:
                continue
            path = artifact["path"]
            referenced_paths.add(path)
            entry = manifest_artifacts.get(path)
            if entry is None:
                raise ValidationError(
                    f"{record['record_id']}: embedded artifact is absent from "
                    f"manifest: {path}"
                )
            if artifact["digest"] != entry["sha256"]:
                raise ValidationError(
                    f"{record['record_id']}: embedded artifact digest does not "
                    f"match manifest: {path}"
                )
            if artifact["media_type"] != entry["media_type"]:
                raise ValidationError(
                    f"{record['record_id']}: embedded artifact media_type does "
                    f"not match manifest: {path}"
                )
    unreferenced = set(manifest_artifacts) - referenced_paths
    if unreferenced:
        raise ValidationError(
            f"manifest artifacts lack Evidence records: {sorted(unreferenced)}"
        )

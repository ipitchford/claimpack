"""Deterministic helpers for producing small ClaimPack fixtures."""

from __future__ import annotations

import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .canonical import pretty_bytes
from .errors import ValidationError
from .ids import claim_id_for, package_root_for, record_id_for, sha256_label
from .reader import validate_relative_path
from .records import MANIFEST_VERSION, validate_record
from .validate import validate_pack


def seal_record(value: dict[str, Any]) -> dict[str, Any]:
    """Copy a record, derive its identities, and validate the sealed result."""

    record = deepcopy(value)
    if record.get("record_type") == "claim-version":
        record["claim_id"] = claim_id_for(record)
    record["record_id"] = record_id_for(record)
    validate_record(record)
    return record


def write_pack(
    destination: str | Path,
    *,
    records: list[dict[str, Any]],
    artifacts: dict[str, tuple[bytes, str]] | None = None,
    created_at: str,
    primary_claim_record_id: str | None = None,
) -> Path:
    """Write and revalidate a new directory pack without overwriting a path."""

    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValidationError(f"refusing to overwrite pack path: {destination}")

    artifacts = artifacts or {}
    record_ids: set[str] = set()
    for record in records:
        validate_record(record)
        if record["record_id"] in record_ids:
            raise ValidationError(f"duplicate record ID: {record['record_id']}")
        record_ids.add(record["record_id"])
    if primary_claim_record_id is not None:
        matching = [
            item for item in records if item["record_id"] == primary_claim_record_id
        ]
        if not matching or matching[0]["record_type"] != "claim-version":
            raise ValidationError(
                "primary_claim_record_id must identify an included ClaimVersion"
            )

    validated_artifacts: dict[str, tuple[bytes, str]] = {}
    for raw_path, value in artifacts.items():
        path = validate_relative_path(raw_path)
        if path != raw_path:
            raise ValidationError(f"artifact path is not canonical: {raw_path!r}")
        if path == "claimpack.json" or path.startswith("records/"):
            raise ValidationError(f"artifact path is reserved: {path}")
        data, media_type = value
        if (
            not isinstance(data, bytes)
            or not isinstance(media_type, str)
            or not media_type
        ):
            raise ValidationError(f"invalid artifact value: {path}")
        validated_artifacts[path] = (data, media_type)

    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.claimpack-stage.",
            dir=destination.parent,
        )
    )
    try:
        result = _write_staged_pack(
            stage,
            records=records,
            artifacts=validated_artifacts,
            created_at=created_at,
            primary_claim_record_id=primary_claim_record_id,
        )
        result.rename(destination)
    except Exception:
        if stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)
        raise
    return destination


def _write_staged_pack(
    destination: Path,
    *,
    records: list[dict[str, Any]],
    artifacts: dict[str, tuple[bytes, str]],
    created_at: str,
    primary_claim_record_id: str | None,
) -> Path:
    """Write a prevalidated pack into a private same-filesystem staging path."""

    manifest_records: list[dict[str, str]] = []
    for index, record in enumerate(records, start=1):
        path = f"records/{index:03d}-{record['record_type']}.json"
        data = pretty_bytes(record)
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest_records.append(
            {
                "media_type": "application/json",
                "path": path,
                "record_id": record["record_id"],
                "record_type": record["record_type"],
                "sha256": sha256_label(data),
            }
        )

    manifest_artifacts: list[dict[str, str]] = []
    for path in sorted(artifacts):
        data, media_type = artifacts[path]
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest_artifacts.append(
            {
                "media_type": media_type,
                "path": path,
                "sha256": sha256_label(data),
            }
        )

    manifest: dict[str, Any] = {
        "artifacts": manifest_artifacts,
        "created_at": created_at,
        "package_root": "",
        "records": manifest_records,
        "schema_version": MANIFEST_VERSION,
    }
    if primary_claim_record_id is not None:
        manifest["extensions"] = {
            "primary_claim_record_id": primary_claim_record_id,
        }
    manifest["package_root"] = package_root_for(manifest)
    (destination / "claimpack.json").write_bytes(pretty_bytes(manifest))
    validate_pack(str(destination))
    return destination

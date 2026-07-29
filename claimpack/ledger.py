"""Append-only local retention of previously observed adverse assessments."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical import pretty_bytes, read_limited_file, strict_loads
from .errors import ValidationError
from .ids import sha256_label
from .policy import adverse_records
from .records import validate_record

LEDGER_VERSION = "claimpack-seen-ledger/0.1"


def empty_ledger() -> dict[str, Any]:
    return {
        "adverse_records": {},
        "schema_version": LEDGER_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _validate_ledger(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("seen-ledger must be an object")
    if set(value) != {"adverse_records", "schema_version", "updated_at"}:
        raise ValidationError("seen-ledger has missing or unknown fields")
    if value["schema_version"] != LEDGER_VERSION:
        raise ValidationError("unsupported seen-ledger version")
    if not isinstance(value["updated_at"], str):
        raise ValidationError("seen-ledger updated_at must be a timestamp string")
    try:
        parsed = datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("missing timezone")
        parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(
            "seen-ledger updated_at is not a valid timestamp"
        ) from exc
    if not isinstance(value["adverse_records"], dict):
        raise ValidationError("seen-ledger adverse_records must be an object")
    for record_id, record in value["adverse_records"].items():
        if not isinstance(record, dict):
            raise ValidationError("seen-ledger adverse record must be an object")
        if record_id != record.get("record_id"):
            raise ValidationError("seen-ledger record key mismatch")
        validate_record(record)
        if record not in adverse_records([record]):
            raise ValidationError(
                "seen-ledger may retain only adverse assessment records"
            )
    return value


def load_ledger_snapshot(path: str | Path) -> tuple[dict[str, Any], str]:
    path = Path(path)
    if not path.exists():
        raise ValidationError(
            "seen-ledger path is missing; use explicit initialization to create it"
        )
    data = read_limited_file(path)
    return _validate_ledger(strict_loads(data)), sha256_label(data)


def load_ledger(path: str | Path) -> dict[str, Any]:
    return load_ledger_snapshot(path)[0]


def ledger_records(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return list(ledger["adverse_records"].values())


def update_ledger(
    ledger: dict[str, Any],
    observed_records: list[dict[str, Any]],
) -> dict[str, Any]:
    retained = dict(ledger["adverse_records"])
    for record in adverse_records(observed_records):
        retained.setdefault(record["record_id"], record)
    return {
        "adverse_records": retained,
        "schema_version": LEDGER_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_ledger(
    path: str | Path,
    ledger: dict[str, Any],
    *,
    expected_digest: str | None,
    create: bool,
) -> None:
    """Atomically install one monotone ledger snapshot with an optimistic guard."""

    path = Path(path)
    _validate_ledger(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    if create:
        if path.exists() or path.is_symlink():
            raise ValidationError(f"refusing to overwrite seen-ledger: {path}")
    else:
        if expected_digest is None:
            raise ValidationError("ledger update requires the prior snapshot digest")
        if not path.exists():
            raise ValidationError("seen-ledger disappeared before update")
        current_digest = sha256_label(read_limited_file(path))
        if current_digest != expected_digest:
            raise ValidationError("seen-ledger changed concurrently; refusing update")

    file_descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.claimpack-ledger.",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(pretty_bytes(ledger))
            handle.flush()
            os.fsync(handle.fileno())
        if create:
            os.link(temporary_path, path)
            temporary_path.unlink()
        else:
            os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

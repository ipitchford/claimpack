"""Content-derived ClaimPack identifiers."""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from typing import Any

from .canonical import canonical_bytes
from .errors import ValidationError


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_label(data: bytes) -> str:
    return f"sha256:{sha256_hex(data)}"


def ni_sha256(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"ni:///sha-256;{encoded}"


def claim_identity_projection(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("record_type") != "claim-version":
        raise ValidationError("claim identity requires a claim-version record")
    try:
        return {
            "protocol_version": record["protocol_version"],
            "record_type": record["record_type"],
            "scope": deepcopy(record["scope"]),
            "statement": deepcopy(record["statement"]),
        }
    except KeyError as exc:
        raise ValidationError(f"claim identity field missing: {exc.args[0]}") from exc


def claim_id_for(record: dict[str, Any]) -> str:
    return ni_sha256(canonical_bytes(claim_identity_projection(record)))


def record_id_for(record: dict[str, Any]) -> str:
    projection = deepcopy(record)
    projection.pop("record_id", None)
    return ni_sha256(canonical_bytes(projection))


def package_root_for(manifest: dict[str, Any]) -> str:
    projection = deepcopy(manifest)
    projection.pop("package_root", None)
    return ni_sha256(canonical_bytes(projection))


def policy_digest_for(policy: dict[str, Any]) -> str:
    projection = deepcopy(policy)
    projection.pop("policy_digest", None)
    return sha256_label(canonical_bytes(projection))

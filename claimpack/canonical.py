"""Restricted canonical JSON used by ClaimPack v0.1.

This is deliberately narrower than general RFC 8785 JCS. Identity-bearing
values may contain only objects, arrays, strings, booleans, and null. Numbers
are represented as strings. Unicode is preserved exactly and never normalized.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .errors import ClaimPackError, LimitError, ParseError

MAX_JSON_BYTES = 1_048_576
MAX_DEPTH = 64
MAX_STRING_CHARS = 262_144
MAX_ARRAY_ITEMS = 4_096
MAX_OBJECT_FIELDS = 1_024


def _reject_duplicate_pairs(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ParseError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def strict_loads(data: bytes | str, *, max_bytes: int = MAX_JSON_BYTES) -> Any:
    """Parse UTF-8 JSON while rejecting duplicates and ambiguous constants."""

    if isinstance(data, str):
        try:
            encoded = data.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ParseError("JSON contains an invalid Unicode surrogate") from exc
        text = data
    else:
        encoded = data
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParseError("JSON must be valid UTF-8") from exc

    if len(encoded) > max_bytes:
        raise LimitError(f"JSON exceeds {max_bytes} bytes")

    def reject_constant(value: str) -> None:
        raise ParseError(f"non-finite JSON number is forbidden: {value}")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=reject_constant,
        )
    except ClaimPackError:
        raise
    except RecursionError as exc:
        raise LimitError("JSON nesting exceeded the parser's safe depth") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ParseError(f"invalid JSON: {exc}") from exc

    validate_restricted_value(value)
    return value


def read_limited_file(
    path: str | Path,
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> bytes:
    """Read at most one byte beyond a declared local-file budget."""

    with Path(path).open("rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise LimitError(f"file exceeds {max_bytes} bytes: {path}")
    return data


def validate_restricted_value(value: Any, *, _depth: int = 0) -> None:
    """Validate the deterministic, number-free ClaimPack canonical profile."""

    if _depth > MAX_DEPTH:
        raise LimitError(f"JSON nesting exceeds {MAX_DEPTH}")

    if value is None or isinstance(value, bool):
        return

    if isinstance(value, str):
        if len(value) > MAX_STRING_CHARS:
            raise LimitError(f"string exceeds {MAX_STRING_CHARS} characters")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ParseError("string contains an invalid Unicode surrogate") from exc
        return

    if isinstance(value, (int, float)):
        raise ParseError(
            "JSON numbers are forbidden in identity-bearing ClaimPack data; "
            "encode quantities as decimal strings"
        )

    if isinstance(value, list):
        if len(value) > MAX_ARRAY_ITEMS:
            raise LimitError(f"array exceeds {MAX_ARRAY_ITEMS} items")
        for item in value:
            validate_restricted_value(item, _depth=_depth + 1)
        return

    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_FIELDS:
            raise LimitError(f"object exceeds {MAX_OBJECT_FIELDS} fields")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ParseError("object keys must be strings")
            if not key.isascii():
                raise ParseError(f"object key must be ASCII: {key!r}")
            validate_restricted_value(item, _depth=_depth + 1)
        return

    raise ParseError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 bytes for a restricted-profile value."""

    validate_restricted_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def pretty_bytes(value: Any) -> bytes:
    """Return stable, readable UTF-8 JSON for checked-in records."""

    validate_restricted_value(value)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

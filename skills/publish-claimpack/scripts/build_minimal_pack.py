#!/usr/bin/env python3
"""Build a new one-ClaimVersion ClaimPack from an explicit JSON draft."""

from __future__ import annotations

import argparse
from pathlib import Path

from claimpack.build import seal_record, write_pack
from claimpack.canonical import read_limited_file, strict_loads


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a minimal one-claim pack at a new destination.",
    )
    parser.add_argument("--claim", required=True, help="Unsealed ClaimVersion JSON.")
    parser.add_argument("--destination", required=True, help="New pack directory.")
    parser.add_argument("--created-at", required=True, help="ISO-8601 timestamp.")
    args = parser.parse_args(argv)

    raw = read_limited_file(args.claim)
    if b"REPLACE_WITH_" in raw:
        raise SystemExit("claim draft still contains REPLACE_WITH_ placeholders")
    value = strict_loads(raw)
    if not isinstance(value, dict) or value.get("record_type") != "claim-version":
        raise SystemExit("--claim must contain one unsealed ClaimVersion object")
    if "record_id" in value or "claim_id" in value:
        raise SystemExit("remove record_id and claim_id; this builder derives them")

    sealed = seal_record(value)
    destination = write_pack(
        Path(args.destination),
        records=[sealed],
        created_at=args.created_at,
        primary_claim_record_id=sealed["record_id"],
    )
    print(destination / "claimpack.json")
    print(sealed["claim_id"])
    print(sealed["record_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

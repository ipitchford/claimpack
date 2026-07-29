"""Command-line interface for the offline ClaimPack consumer."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical import pretty_bytes, read_limited_file, strict_loads
from .catalog import diff_catalogs
from .errors import ClaimPackError
from .ledger import (
    empty_ledger,
    ledger_records,
    load_ledger_snapshot,
    update_ledger,
    write_ledger,
)
from .policy import evaluate_pack
from .receipt import create_use_receipt
from .records import validate_policy
from .validate import validate_pack


def _policy(path: str) -> dict[str, Any]:
    value = strict_loads(read_limited_file(path))
    if not isinstance(value, dict):
        raise ValueError("policy must be a JSON object")
    validate_policy(value)
    return value


def _as_of(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--as-of must include a timezone")
    return parsed


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _atomic_create(path: Path, data: bytes) -> None:
    """Install a new file atomically and never replace an existing path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.claimpack-new.",
        dir=path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary_path, path)
        temporary_path.unlink()
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _cmd_validate(args: argparse.Namespace) -> int:
    pack = validate_pack(args.pack)
    _print(
        {
            "claim_count": len(pack.claims()),
            "package_root": pack.package_root,
            "record_count": len(pack.records),
            "source": pack.source,
            "structurally_valid": True,
            "truth_certified": False,
        }
    )
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    pack = validate_pack(args.pack)
    claims = []
    evidence = []
    relations = []
    assessments = []
    for claim in pack.claims():
        claims.append(
            {
                "aliases": claim["aliases"],
                "claim_id": claim["claim_id"],
                "claim_kind": claim["scope"]["claim_kind"],
                "claim_record_id": claim["record_id"],
                "dependency_targets": claim["dependency_targets"],
                "latex": claim["statement"]["latex"],
                "natural": claim["statement"]["natural"],
                "non_implications": claim["scope"]["non_implications"],
                "sources": claim["sources"],
            }
        )
    for record in pack.records.values():
        if record["record_type"] == "evidence":
            evidence.append(
                {
                    "artifacts": [
                        {
                            "digest": artifact["digest"],
                            "embedded": artifact["embedded"],
                            "locator": artifact.get("locator", ""),
                            "name": artifact["name"],
                            "path": artifact.get("path", ""),
                        }
                        for artifact in record["artifacts"]
                    ],
                    "coverage": record["coverage"],
                    "evidence_kind": record["evidence_kind"],
                    "issuer": record["issuer"],
                    "limitations": record["limitations"],
                    "record_id": record["record_id"],
                    "replay": {
                        "display_only": record["replay"]["display_only"],
                        "quoted_source_package_command": record["replay"]["command"],
                    },
                    "subject": record["subject"],
                }
            )
        elif record["record_type"] == "relation":
            relations.append(
                {
                    "load_bearing": record["load_bearing"],
                    "record_id": record["record_id"],
                    "relation": record["relation"],
                    "semantic_alignment": record["semantic_alignment"],
                    "source": record["source"],
                    "target": record["target"],
                }
            )
        elif record["record_type"] == "assessment":
            assessments.append(
                {
                    "assessment_kind": record["assessment_kind"],
                    "authentication": record["authentication"],
                    "dimension": record["dimension"],
                    "evidence_refs": record["evidence_refs"],
                    "independence": record["independence"],
                    "issuer": record["issuer"],
                    "outcome": record["outcome"],
                    "qualifications": record["qualifications"],
                    "record_id": record["record_id"],
                    "stance": record["stance"],
                    "summary": record["summary"],
                    "target": record["target"],
                }
            )
    _print(
        {
            "assessments": sorted(assessments, key=lambda item: item["record_id"]),
            "claims": claims,
            "evidence": sorted(evidence, key=lambda item: item["record_id"]),
            "notice": (
                "Package text and commands were treated as inert data. "
                "Structural validity is not scientific verification."
            ),
            "package_root": pack.package_root,
            "primary_claim_record_id": (
                pack.primary_claim()["record_id"]
                if pack.primary_claim() is not None
                else None
            ),
            "relations": sorted(relations, key=lambda item: item["record_id"]),
        }
    )
    return 0


def _cmd_decide(args: argparse.Namespace) -> int:
    if args.update_ledger and not args.seen_ledger:
        raise ValueError("--update-ledger requires --seen-ledger")
    if args.init_ledger and not (args.seen_ledger and args.update_ledger):
        raise ValueError(
            "--init-ledger requires both --seen-ledger and --update-ledger"
        )

    retrieved_at = datetime.now(timezone.utc)
    receipt_path = Path(args.receipt).expanduser().resolve() if args.receipt else None
    ledger_path = (
        Path(args.seen_ledger).expanduser().resolve() if args.seen_ledger else None
    )
    if (
        receipt_path is not None
        and ledger_path is not None
        and receipt_path == ledger_path
    ):
        raise ValueError("--receipt and --seen-ledger must be distinct paths")
    if receipt_path is not None and (
        receipt_path.exists() or receipt_path.is_symlink()
    ):
        raise ValueError(f"refusing to overwrite receipt: {receipt_path}")

    ledger = None
    ledger_digest = None
    if ledger_path is not None:
        if args.init_ledger:
            if ledger_path.exists() or ledger_path.is_symlink():
                raise ValueError(
                    f"refusing to initialize existing seen-ledger: {ledger_path}"
                )
            ledger = empty_ledger()
        else:
            ledger, ledger_digest = load_ledger_snapshot(ledger_path)
    if receipt_path is not None:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)

    pack = validate_pack(args.pack)
    policy = _policy(args.policy)
    policy_as_of = _as_of(args.as_of) or retrieved_at
    evaluation = evaluate_pack(
        pack,
        policy,
        claim_record_id=args.claim_record_id,
        as_of=policy_as_of,
        ledger_records=ledger_records(ledger) if ledger else None,
        objection_search_complete=args.objection_search_complete,
        objection_search_context=args.objection_search_context,
        authenticated_record_ids=set(args.authenticated_record_id),
        authentication_context=args.authentication_context,
    )
    claim = next(
        item
        for item in pack.claims()
        if item["record_id"] == evaluation.claim_record_id
    )
    receipt = create_use_receipt(
        pack,
        claim,
        policy,
        evaluation,
        purpose=args.purpose,
        consumer_name=args.consumer_name,
        consumer_version=args.consumer_version,
        consumer_run_id=args.consumer_run_id,
        consumer_model=args.consumer_model,
        routes=[f"local:{pack.source}"],
        catalogue_head=args.catalogue_head,
        retrieved_at=retrieved_at.isoformat(),
        parent_receipt_id=args.parent_receipt_id,
        source_run_id=args.source_run_id,
    )

    if args.update_ledger:
        assert ledger_path is not None
        assert ledger is not None
        updated = update_ledger(
            ledger,
            list(pack.records.values()),
        )
        write_ledger(
            ledger_path,
            updated,
            expected_digest=ledger_digest,
            create=args.init_ledger,
        )

    if receipt_path is not None:
        _atomic_create(receipt_path, pretty_bytes(receipt))

    if receipt_path is None:
        _print(receipt)
    else:
        _print(
            {
                "decision": evaluation.decision.value,
                "limits_hit": list(evaluation.limits_hit),
                "receipt": str(receipt_path),
                "receipt_record_id": receipt["record_id"],
                "termination_reason": evaluation.termination_reason,
            }
        )
    return 0


def _cmd_catalog_diff(args: argparse.Namespace) -> int:
    older = strict_loads(read_limited_file(args.older))
    newer = strict_loads(read_limited_file(args.newer))
    if not isinstance(older, dict) or not isinstance(newer, dict):
        raise ValueError("catalog snapshots must be JSON objects")
    _print(diff_catalogs(older, newer))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claimpack",
        description="Offline, non-executing ClaimPack v0.1 consumer",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("pack")
    validate.set_defaults(handler=_cmd_validate)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("pack")
    inspect.set_defaults(handler=_cmd_inspect)

    catalog_diff = subparsers.add_parser("catalog-diff")
    catalog_diff.add_argument("older")
    catalog_diff.add_argument("newer")
    catalog_diff.set_defaults(handler=_cmd_catalog_diff)

    decide = subparsers.add_parser("decide")
    decide.add_argument("pack")
    decide.add_argument("--policy", required=True)
    decide.add_argument(
        "--receipt",
        help=(
            "persist the UseReceipt at this new path; when omitted, print the "
            "complete receipt to stdout without writing it"
        ),
    )
    decide.add_argument("--purpose", default="research discovery and triage")
    decide.add_argument("--claim-record-id")
    decide.add_argument("--as-of")
    decide.add_argument("--seen-ledger")
    decide.add_argument("--update-ledger", action="store_true")
    decide.add_argument(
        "--init-ledger",
        action="store_true",
        help="explicitly create a missing seen-ledger; requires --update-ledger",
    )
    decide.add_argument(
        "--catalogue-head",
        default="",
        help="exact catalogue snapshot head actually used; empty for direct local input",
    )
    decide.add_argument(
        "--authenticated-record-id",
        action="append",
        default=[],
        help="assessment record ID authenticated outside the package",
    )
    decide.add_argument("--authentication-context", default="")
    decide.add_argument("--objection-search-complete", action="store_true")
    decide.add_argument("--objection-search-context", default="")
    decide.add_argument("--consumer-name", default="claimpack")
    decide.add_argument("--consumer-version", default="0.1.0.dev0")
    decide.add_argument("--consumer-run-id", default="")
    decide.add_argument("--consumer-model", default="")
    decide.add_argument("--parent-receipt-id", default="")
    decide.add_argument("--source-run-id", default="")
    decide.set_defaults(handler=_cmd_decide)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        return int(args.handler(args))
    except (ClaimPackError, OSError, ValueError) as exc:
        print(f"claimpack: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import unittest

from claimpack.canonical import canonical_bytes
from claimpack.catalog import diff_catalogs
from claimpack.ids import ni_sha256, sha256_label


def catalog(head: str, entries: list[dict]) -> dict:
    value = {
        "catalog_head": "",
        "entries": entries,
        "generated_at": f"2026-07-29T00:00:0{len(head)}+00:00",
        "schema_version": "claimpack-static-catalog/0.1",
        "search_fingerprint_profile": "test",
    }
    projection = dict(value)
    projection.pop("catalog_head")
    value["catalog_head"] = ni_sha256(canonical_bytes(projection))
    return value


def entry(label: str, packages: list[dict] | None = None) -> dict:
    return {
        "aliases": [f"{label} alias"],
        "assessment_record_ids": [],
        "author_claimed_status": "unassessed",
        "canonical_status": "unassessed",
        "claim_id": ni_sha256(f"{label}:claim".encode()),
        "claim_kind": "full-result",
        "claim_record_id": ni_sha256(f"{label}:record".encode()),
        "formal_verification_status": "unassessed",
        "human_review_status": "unassessed",
        "independent_reproduction_status": "unassessed",
        "latex": "",
        "natural": f"{label} statement",
        "novelty_status": "unassessed",
        "objection_record_ids": [],
        "packages": packages or [],
        "search_fingerprint": sha256_label(f"{label}:search".encode()),
        "sources": [],
        "status_updated_at": "2026-07-29T00:00:00+00:00",
        "system_assessment": "unassessed",
    }


class CatalogTests(unittest.TestCase):
    def test_disappearance_is_not_called_retraction(self) -> None:
        old_entry = entry("old")
        result = diff_catalogs(
            catalog("old", [old_entry]),
            catalog("new", []),
        )
        self.assertEqual(result["events"][0]["event"], "claim-record-disappeared")
        self.assertIn("do not infer", result["events"][0]["meaning"])

    def test_addition_and_package_change_are_explicit(self) -> None:
        old = entry(
            "changed",
            [
                {
                    "package_root": ni_sha256(b"old package"),
                    "path": "examples/old",
                    "primary": True,
                }
            ],
        )
        new = {
            **old,
            "packages": [
                {
                    "package_root": ni_sha256(b"new package"),
                    "path": "examples/new",
                    "primary": True,
                }
            ],
        }
        added = entry("added")
        events = diff_catalogs(
            catalog("old", [old]),
            catalog("new", [new, added]),
        )["events"]
        self.assertEqual(
            {event["event"] for event in events},
            {"claim-record-added", "package-binding-changed"},
        )


if __name__ == "__main__":
    unittest.main()

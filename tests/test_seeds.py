from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from claimpack.canonical import canonical_bytes, strict_loads
from claimpack.ids import claim_identity_projection, ni_sha256
from claimpack.policy import Decision, evaluate_pack
from claimpack.records import validate_policy
from claimpack.validate import validate_pack

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_SEEDS = {
    "z20": {
        "archive_digest": "sha256:2b92e5febf5deaeb86db96ef37ddd7df33ac4022453090291c72633fda0310e5",
        "claim_id": "ni:///sha-256;Z-cg7u8IqgNBCzyBxktrKSXpD7XWXhkiYwHAPVza6aQ",
        "package_root": "ni:///sha-256;qMJxdeZaeOoJ0NiWTJoHhSOPEPI5055jRP7E0x14Ce8",
        "statement": "The maximum cochromatic number among graphs on 20 vertices is 6.",
    },
    "vr2-k4": {
        "archive_digest": "sha256:e14178610233f9e5960da06162e07f3a0ce9aa65799dff3d456958a417997f4f",
        "claim_id": "ni:///sha-256;cDwAiv3p8UiaXGlcLfx5Ef_2Kgf1NM3j9XhkxGxFkis",
        "package_root": "ni:///sha-256;Q3GoAq97GN-Q7B-vgySsFkDb_KzqVn4xJkvaLs6E-lg",
        "statement": (
            "The least n such that every red-blue edge-colouring of K_n "
            "contains two vertex-disjoint monochromatic copies of K_4 is 20; "
            "the copies need not have the same colour."
        ),
    },
    "erdos848": {
        "archive_digest": "sha256:fcd83b8986bf55784cf97513513d628af1fa5fe3bb0a2bdb869e1307dbbb8060",
        "claim_id": "ni:///sha-256;uq0CpkvtJk1BMan7aaViTjjY4lLDwSL8uk2hHJvE1m8",
        "package_root": "ni:///sha-256;HdKwXmxdjS-bofAsGXc_XbG0WKIUWKoT86wU5RTx5Bc",
        "statement": (
            "For every positive integer N, the maximum size f(N) of a subset "
            "A of {1,...,N} such that ab+1 is nonsquarefree for every a,b in "
            "A, including a=b, equals floor((N+18)/25)."
        ),
    },
}


class SeedTests(unittest.TestCase):
    def test_reference_packs_are_valid_but_not_truth_certificates(self) -> None:
        policy = strict_loads(
            (ROOT / "policies/cautious-scientific-use-v0.1.json").read_bytes()
        )
        validate_policy(policy)
        for name in ["z20", "vr2-k4", "erdos848"]:
            with self.subTest(name=name):
                pack = validate_pack(str(ROOT / "examples" / name))
                self.assertIsNotNone(pack.primary_claim())
                evaluation = evaluate_pack(
                    pack,
                    policy,
                    as_of=datetime(2026, 7, 29, 13, 0, tzinfo=timezone.utc),
                )
                self.assertEqual(evaluation.decision, Decision.UNKNOWN)

    def test_exact_seed_statements_and_archival_digests(self) -> None:
        for name, expected in EXPECTED_SEEDS.items():
            with self.subTest(name=name):
                claim = validate_pack(str(ROOT / "examples" / name)).primary_claim()
                self.assertEqual(claim["statement"]["natural"], expected["statement"])
                self.assertEqual(
                    claim["sources"][0]["digest"], expected["archive_digest"]
                )
                self.assertEqual(claim["claim_id"], expected["claim_id"])

    def test_catalog_head_and_package_roots_are_exact(self) -> None:
        catalog = strict_loads((ROOT / "catalog/catalog.json").read_bytes())
        projection = dict(catalog)
        projection.pop("catalog_head")
        self.assertEqual(
            catalog["catalog_head"], ni_sha256(canonical_bytes(projection))
        )
        for entry in catalog["entries"]:
            for package in entry["packages"]:
                pack = validate_pack(str(ROOT / package["path"]))
                self.assertEqual(package["package_root"], pack.package_root)
                self.assertIn(entry["claim_record_id"], pack.records)
        for name, expected in EXPECTED_SEEDS.items():
            pack = validate_pack(str(ROOT / "examples" / name))
            self.assertEqual(pack.package_root, expected["package_root"])

    def test_fixed_core_claim_is_deduplicated_by_identity(self) -> None:
        z20 = validate_pack(str(ROOT / "examples/z20"))
        vr2 = validate_pack(str(ROOT / "examples/vr2-k4"))
        z20_dependency = z20.primary_claim()["dependency_targets"][0]["record_id"]
        vr2_dependency = vr2.primary_claim()["dependency_targets"][0]["record_id"]
        self.assertEqual(z20_dependency, vr2_dependency)
        self.assertEqual(
            z20.records[z20_dependency]["claim_id"],
            "ni:///sha-256;XZiVDafrILfPSxDvR1kHHCr5Cfk_gEKmC-WAOzVi9xg",
        )

    def test_seed_claim_identity_excludes_assurance_status_language(self) -> None:
        forbidden = {
            "candidate release",
            "candidate status",
            "candidate-claim",
            "end-to-end formalization",
            "end-to-end formalisation",
            "gapless range ledger",
            "independent external reproduction",
            "independently verify",
            "local replay",
            "not bundled",
            "not relicensed",
            "peer review",
            "truth certification",
        }
        for name in ["z20", "vr2-k4", "erdos848"]:
            pack = validate_pack(str(ROOT / "examples" / name))
            for claim in pack.claims():
                with self.subTest(name=name, record_id=claim["record_id"]):
                    projection = canonical_bytes(
                        claim_identity_projection(claim)
                    ).decode("utf-8")
                    for phrase in forbidden:
                        self.assertNotIn(phrase, projection.casefold())


if __name__ == "__main__":
    unittest.main()

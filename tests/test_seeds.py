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

DEGREE_THEOREM_STATEMENT = (
    "Let r,s>=1 and choose the standard monomial coefficient orders on V_r, "
    "V_s, and V_{r+s}. For Phi_{r,s}(A,B)=(AB,Res(A,B)), det D "
    "Phi_{r,s}=(-1)^{s(r+1)}(r-s)Res(A,B)^2. In particular, if r!=s, "
    "Phi_{r,s} is etale on the coprime locus {Res!=0}. For nonzero ell in "
    "V_{r+s}^*, if r!=s, projectivisation is a finite etale "
    "mu_{|s-r|}-torsor from the normalized slice tilde X_{r,s,ell} to "
    "U_{r,s,ell}; the induced multiplication map has generic degree |s-r| "
    "binom(r+s,r); and, if the resultant divisor R_{r,s} and "
    "multiplication-hyperplane divisor S_{r,s,ell} are prime, "
    "Cl(U_{r,s,ell}) is isomorphic to Z/|s-r|Z."
)

DEGREE_CUBIC_STATEMENT = (
    "Let 0!=ell in V_3^*, let Gamma={[M^3]:[M] in P(V_1)} be the twisted "
    "cubic, let H_ell=P(ker ell), and let X_ell be the normalized "
    "linear-quadratic slice. Over C, X_ell is isomorphic to A^3 if and only "
    "if H_ell is tangent but not osculating to Gamma. More precisely, three "
    "distinct intersection points give X_ell not isomorphic to A^3 with "
    "class L^3-L; tangent nonosculating contact gives X_ell isomorphic to "
    "A^3 with class L^3; and osculating contact gives X_ell isomorphic to "
    "G_m x A^2 with class L^3-L^2. Equivalently, the successful functionals "
    "form the discriminant surface of binary cubics with the triple-root "
    "curve removed."
)

EXOTIC_TRANSVERSE_STATEMENT = (
    "Every transverse normalized linear-quadratic slice is isomorphic to "
    "X(4,4,-a^3+a^2b^2-b^3), the nontrivial G_a-bundle over A^2 minus {0} "
    "represented by the Cech cocycle -1/(ab^4)+1/(a^2b^2)-1/(a^4b). Its "
    "total space is an exotic affine three-sphere and is not algebraically "
    "isomorphic to SL_2(C)."
)

EXOTIC_UNIVERSAL_STATEMENT = (
    "For every nonzero ell in V_5^*, the normalized quadratic-cubic slice "
    "X_ell^{2,3} is not isomorphic to A^5. More precisely, if L=[A^1] and "
    "the reduced degeneracy loci K,D_2,D_1,Z are those defined in the "
    "manuscript, then [X_ell^{2,3}]=L^5-L^3-L^3[K]+L([D_2]-[D_1])+L^2[Z] "
    "in K_0(Var_C), and the compactly supported Hodge-Deligne polynomial of "
    "the right-hand side is never (uv)^5."
)

REDUCIBILITY_STATEMENT = (
    "Let m>=2 and 0!=ell in V_{2m+1}^*. The marked-common-root divisor D_ell "
    "is reducible set-theoretically if and only if [ell] lies in the tangent "
    "developable of the rational normal curve nu_{2m+1}. More precisely: an "
    "evaluation functional gives three reduced irreducible components; a "
    "functional on a punctured tangent line gives exactly two; a genuine "
    "two-point secant functional gives an irreducible divisor; and every "
    "functional with middle-catalecticant rank at least three gives an "
    "irreducible divisor."
)

ADJACENT_HODGE_STATEMENT = (
    "Let m>=2, 0!=ell in V_{2m+1}^*, and rho=rank C_ell. Then "
    "E_c(X_ell^{m,m+1};u,v)!=(uv)^{2m+1}. More precisely, for rho=1 the "
    "polynomial is (uv)^{2m+1}-(uv)^{2m}; for catalecticant rank two of "
    "two-point secant type the coefficient of u^{2m-1}v^{2m-1} is -2; for "
    "rank two of first-jet type it is -1; and for rho>=3 it is -1. "
    "Consequently X_ell^{m,m+1} is not isomorphic to A^{2m+1} for every "
    "such m and ell."
)

CONDITIONAL_ISOLATION_STATEMENT = (
    "Let r,s>=1 and 0!=ell in V_{r+s}^*. If |r-s|>=2, then "
    "X_ell^{r,s}(C) is not contractible. If {r,s}={m,m+1} with m>=2, then "
    "X_ell^{r,s} is not isomorphic to A^{2m+1}. If r=s, relative scaling "
    "gives positive-dimensional fibres and the multiplication-resultant "
    "architecture cannot yield a Keller map. Conditional on the complete "
    "cubic classification in the pinned unrefereed degree-difference "
    "candidate, the tangent nonosculating (1,2) slice and its swapped form "
    "are the unique positive-bidegree normalized affine-space sources in "
    "this architecture that carry a nonzero constant Jacobian determinant."
)

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
    "degree-difference-affine-slices": {
        "archive_digest": "sha256:8d0b0cfb3b43e3b7c7f32f62506ae66e824890e15a981b8498d41a07b4c2fe43",
        "claim_id": "ni:///sha-256;2YnlMQMojvdBY5qY33uMJmO_d7zea8Uj-nGfyPUyyQ4",
        "package_root": "ni:///sha-256;Np_aLDz3rMs1sQ1--lJqCUbuDeu40hUcbaZaosUq3CM",
        "statement": DEGREE_THEOREM_STATEMENT,
    },
    "exotic-affine-spheres-quadratic-cubic": {
        "archive_digest": "sha256:de92abd2033cf65a2412cb070edd388ae2c3fd0d85a08660954d45408343d737",
        "claim_id": "ni:///sha-256;xOVckH4uZ96baKo3neAzm7yelN-4ap8cREGWNPW4fRA",
        "package_root": "ni:///sha-256;Du3Dbg1YN0ds4amIemi3liwh47_Jel2QxzavMUKZL08",
        "statement": EXOTIC_UNIVERSAL_STATEMENT,
    },
    "reducible-incidence-divisors-affine-slices": {
        "archive_digest": "sha256:b733f4db720495fc9654e83a45fc7d77edc9a72a225b919e436cdf2ce924fbc9",
        "claim_id": "ni:///sha-256;7wV20SW1VjqzO2MJwLRjy93gidN10nje-Jl3lHLuspA",
        "package_root": "ni:///sha-256;HqZkyPBy34OpXnas8qQKrhyEL9AR4deTzMRqJMKi8tw",
        "statement": ADJACENT_HODGE_STATEMENT,
    },
}

EXPECTED_NEW_CLAIMS = {
    "degree-difference-affine-slices": {
        DEGREE_THEOREM_STATEMENT: {
            "claim_id": "ni:///sha-256;2YnlMQMojvdBY5qY33uMJmO_d7zea8Uj-nGfyPUyyQ4",
            "record_id": "ni:///sha-256;ukCJErI26rVkXt9rTP-BKnuI_o-nAW4-OSUVoYbIVus",
        },
        DEGREE_CUBIC_STATEMENT: {
            "claim_id": "ni:///sha-256;eOEoKPPS6zGsnijrO1-ggnWoegNb13LigIKO6RmQG0w",
            "record_id": "ni:///sha-256;e4KmJmxZNpIiwxsySUXDXoyQRAOUf2CRCpPzwvUuMTI",
        },
    },
    "exotic-affine-spheres-quadratic-cubic": {
        EXOTIC_TRANSVERSE_STATEMENT: {
            "claim_id": "ni:///sha-256;DH0vVa2vg0jxlJ7F_4jknLdDr6_U2LWI0BdDzYg43tg",
            "record_id": "ni:///sha-256;6CJVmZckc9uvUHqEJK9goXPO1KqVRPQDmfaP-nya4fw",
        },
        EXOTIC_UNIVERSAL_STATEMENT: {
            "claim_id": "ni:///sha-256;xOVckH4uZ96baKo3neAzm7yelN-4ap8cREGWNPW4fRA",
            "record_id": "ni:///sha-256;NL03Ca0XN805qQ9dy00FubtyO9ohIVWX-H4k5yPNFJY",
        },
    },
    "reducible-incidence-divisors-affine-slices": {
        REDUCIBILITY_STATEMENT: {
            "claim_id": "ni:///sha-256;sxYzS5cJ3rEiYLV92ojE7AzsCDV8ZV1y_8JgkNYnAkY",
            "record_id": "ni:///sha-256;xHpxUzjaok3i7Ac44k2UOVGMIrgK6j2T-1QgurwBDAM",
        },
        ADJACENT_HODGE_STATEMENT: {
            "claim_id": "ni:///sha-256;7wV20SW1VjqzO2MJwLRjy93gidN10nje-Jl3lHLuspA",
            "record_id": "ni:///sha-256;fYYFbxy8A7KxihhKUEM6NRkaapRATE_I1gWxEoJz1ew",
        },
        CONDITIONAL_ISOLATION_STATEMENT: {
            "claim_id": "ni:///sha-256;5CJftn3xNkybF2NCnp_CTBOmPDHTCVXC_rGTQWEeGd8",
            "record_id": "ni:///sha-256;5nhOT3cyu2_jUDqEdxOVTiyPxPZqu4mPhTIVNDSzd7o",
        },
    },
}


class SeedTests(unittest.TestCase):
    def test_reference_packs_are_valid_but_not_truth_certificates(self) -> None:
        policy = strict_loads(
            (ROOT / "policies/cautious-scientific-use-v0.1.json").read_bytes()
        )
        validate_policy(policy)
        for name in EXPECTED_SEEDS:
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

    def test_new_seed_claim_statements_and_identities_are_exact(self) -> None:
        for name, expected_claims in EXPECTED_NEW_CLAIMS.items():
            with self.subTest(name=name):
                pack = validate_pack(str(ROOT / "examples" / name))
                actual = {
                    claim["statement"]["natural"]: claim for claim in pack.claims()
                }
                for statement, expected in expected_claims.items():
                    self.assertIn(statement, actual)
                    self.assertEqual(actual[statement]["claim_id"], expected["claim_id"])
                    self.assertEqual(
                        actual[statement]["record_id"], expected["record_id"]
                    )

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

    def test_new_seed_dependencies_are_exact_and_deduplicated(self) -> None:
        degree = validate_pack(str(ROOT / "examples/degree-difference-affine-slices"))
        exotic = validate_pack(
            str(ROOT / "examples/exotic-affine-spheres-quadratic-cubic")
        )
        reducible = validate_pack(
            str(ROOT / "examples/reducible-incidence-divisors-affine-slices")
        )

        degree_by_statement = {
            claim["statement"]["natural"]: claim for claim in degree.claims()
        }
        exotic_by_statement = {
            claim["statement"]["natural"]: claim for claim in exotic.claims()
        }
        reducible_by_statement = {
            claim["statement"]["natural"]: claim for claim in reducible.claims()
        }

        degree_theorem = degree_by_statement[DEGREE_THEOREM_STATEMENT]
        degree_cubic = degree_by_statement[DEGREE_CUBIC_STATEMENT]
        exotic_transverse = exotic_by_statement[EXOTIC_TRANSVERSE_STATEMENT]
        exotic_universal = exotic_by_statement[EXOTIC_UNIVERSAL_STATEMENT]
        reducibility = reducible_by_statement[REDUCIBILITY_STATEMENT]
        adjacent_hodge = reducible_by_statement[ADJACENT_HODGE_STATEMENT]
        conditional_isolation = reducible_by_statement[
            CONDITIONAL_ISOLATION_STATEMENT
        ]

        self.assertEqual(
            exotic_transverse["dependency_targets"],
            [
                {
                    "record_id": degree_cubic["record_id"],
                    "record_type": "claim-version",
                }
            ],
        )
        self.assertEqual(exotic_universal["dependency_targets"], [])
        self.assertEqual(
            exotic.records[degree_cubic["record_id"]]["claim_id"],
            degree_cubic["claim_id"],
        )

        self.assertEqual(
            adjacent_hodge["dependency_targets"],
            [
                {
                    "record_id": reducibility["record_id"],
                    "record_type": "claim-version",
                }
            ],
        )
        self.assertEqual(
            {target["record_id"] for target in conditional_isolation["dependency_targets"]},
            {
                adjacent_hodge["record_id"],
                degree_theorem["record_id"],
                degree_cubic["record_id"],
            },
        )
        self.assertEqual(
            reducible.records[degree_theorem["record_id"]]["claim_id"],
            degree_theorem["claim_id"],
        )
        self.assertEqual(
            reducible.records[degree_cubic["record_id"]]["claim_id"],
            degree_cubic["claim_id"],
        )

    def test_new_dependency_targets_have_partial_semantic_relations(self) -> None:
        for name in EXPECTED_NEW_CLAIMS:
            pack = validate_pack(str(ROOT / "examples" / name))
            relations = [
                record
                for record in pack.records.values()
                if record["record_type"] == "relation"
                and record["relation"] == "depends-on"
            ]
            for claim in pack.claims():
                for target in claim["dependency_targets"]:
                    with self.subTest(
                        name=name,
                        source=claim["record_id"],
                        target=target["record_id"],
                    ):
                        matches = [
                            relation
                            for relation in relations
                            if relation["source"]["record_id"]
                            == claim["record_id"]
                            and relation["target"] == target
                        ]
                        self.assertEqual(len(matches), 1)
                        self.assertTrue(matches[0]["load_bearing"])
                        self.assertEqual(
                            matches[0]["semantic_alignment"]["status"], "partial"
                        )

    def test_catalog_deduplicates_shared_new_claims(self) -> None:
        catalog = strict_loads((ROOT / "catalog/catalog.json").read_bytes())
        entries = {entry["claim_record_id"]: entry for entry in catalog["entries"]}
        degree_claims = EXPECTED_NEW_CLAIMS["degree-difference-affine-slices"]
        degree_theorem_id = degree_claims[DEGREE_THEOREM_STATEMENT]["record_id"]
        degree_cubic_id = degree_claims[DEGREE_CUBIC_STATEMENT]["record_id"]
        self.assertEqual(
            {package["path"] for package in entries[degree_theorem_id]["packages"]},
            {
                "examples/degree-difference-affine-slices",
                "examples/reducible-incidence-divisors-affine-slices",
            },
        )
        self.assertEqual(
            {package["path"] for package in entries[degree_cubic_id]["packages"]},
            {
                "examples/degree-difference-affine-slices",
                "examples/exotic-affine-spheres-quadratic-cubic",
                "examples/reducible-incidence-divisors-affine-slices",
            },
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
        for name in EXPECTED_SEEDS:
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

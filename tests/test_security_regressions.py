from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from claimpack.build import seal_record, write_pack
from claimpack.canonical import pretty_bytes, strict_loads
from claimpack.catalog import validate_catalog
from claimpack.cli import main
from claimpack.errors import PolicyError, ValidationError
from claimpack.ids import ni_sha256, policy_digest_for, record_id_for
from claimpack.ledger import empty_ledger, load_ledger
from claimpack.policy import Decision, evaluate_pack
from claimpack.reader import PackReader
from claimpack.receipt import create_use_receipt, verify_use_receipt
from claimpack.validate import validate_pack

from tests.helpers import (
    NOW,
    demo_components,
    make_assessment,
    make_claim,
    make_evidence,
    make_objection,
    make_policy,
    make_relation,
    make_withdrawal,
    write_demo,
)

ROOT = Path(__file__).resolve().parents[1]
AS_OF = datetime(2026, 7, 29, 14, 0, tzinfo=timezone.utc)


def evaluate_demo(
    path: Path,
    assessments: list[dict],
    *,
    extra_authenticated: list[str] | None = None,
    ledger_records: list[dict] | None = None,
    policy: dict | None = None,
):
    authenticated = {item["record_id"] for item in assessments}
    authenticated.update(extra_authenticated or [])
    return evaluate_pack(
        validate_pack(str(path)),
        policy or make_policy(),
        as_of=AS_OF,
        ledger_records=ledger_records,
        objection_search_complete=True,
        objection_search_context="bounded synthetic snapshot",
        authenticated_record_ids=authenticated,
        authentication_context="synthetic external trust root",
    )


class SecurityRegressionTests(unittest.TestCase):
    def test_transitive_changed_claim_lineage_retains_old_objection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = make_claim(natural="Original exact statement.")
            middle = make_claim(
                natural="Materially revised intermediate statement.",
                lineage=[{"record_id": old["record_id"], "relation": "revises"}],
            )
            new = make_claim(
                natural="Materially revised final statement.",
                lineage=[{"record_id": middle["record_id"], "relation": "revises"}],
            )
            objection = make_objection(old)
            data = b"new claim evidence\n"
            evidence = make_evidence(new, data)
            assessments = [
                make_assessment(
                    new,
                    dimension=dimension,
                    evidence_refs=[evidence["record_id"]],
                )
                for dimension in [
                    "dependency-closure",
                    "known-objections",
                    "statement-precision",
                ]
            ]
            pack_path = write_demo(
                root / "pack",
                claim=new,
                evidence=evidence,
                assessments=assessments,
                artifacts={"artifacts/evidence.txt": (data, "text/plain")},
                extra_records=[old, middle],
            )

            evaluation = evaluate_demo(
                pack_path,
                assessments,
                ledger_records=[objection],
            )
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertIn(
                objection["record_id"],
                {item["record_id"] for item in evaluation.used_records},
            )
            self.assertIn(
                "retain objection qualification",
                evaluation.qualifications,
            )

    def test_evidence_after_assessment_cannot_support_allow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = make_claim()
            data = b"future evidence\n"
            ordinary = make_evidence(claim, data)
            future_evidence = seal_record(
                {
                    **{
                        key: value
                        for key, value in ordinary.items()
                        if key != "record_id"
                    },
                    "issued_at": "2026-07-29T13:00:00+00:00",
                }
            )
            assessments = [
                make_assessment(
                    claim,
                    dimension=dimension,
                    issued_at=NOW,
                    evidence_refs=[future_evidence["record_id"]],
                )
                for dimension in [
                    "dependency-closure",
                    "known-objections",
                    "statement-precision",
                ]
            ]
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=future_evidence,
                assessments=assessments,
                artifacts={"artifacts/evidence.txt": (data, "text/plain")},
            )

            evaluation = evaluate_demo(pack_path, assessments)
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertTrue(
                any(
                    "postdates its assessment" in basis
                    for result in evaluation.dimension_results.values()
                    for basis in result.basis
                )
            )

    def test_future_relation_cannot_close_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency = make_claim(natural="Dependency claim.")
            dependency_data = b"dependency\n"
            dependency_evidence = make_evidence(
                dependency,
                dependency_data,
                path="artifacts/dependency.txt",
            )
            dependency_assessments = [
                make_assessment(
                    dependency,
                    dimension=dimension,
                    evidence_refs=[dependency_evidence["record_id"]],
                )
                for dimension in ["dependency-closure", "statement-precision"]
            ]
            main, main_evidence, main_assessments, main_artifacts = demo_components(
                dependency_targets=[
                    {
                        "record_id": dependency["record_id"],
                        "record_type": "claim-version",
                    }
                ]
            )
            ordinary_relation = make_relation(main, dependency)
            future_relation = seal_record(
                {
                    **{
                        key: value
                        for key, value in ordinary_relation.items()
                        if key != "record_id"
                    },
                    "issued_at": "2026-07-29T15:00:00+00:00",
                }
            )
            relation_data = b"relation\n"
            relation_evidence = make_evidence(
                future_relation,
                relation_data,
                path="artifacts/relation.txt",
            )
            relation_assessment = make_assessment(
                future_relation,
                dimension="semantic-scope-match",
                assessment_kind="correspondence",
                evidence_refs=[relation_evidence["record_id"]],
            )
            pack_path = write_pack(
                root / "pack",
                records=[
                    dependency,
                    dependency_evidence,
                    *dependency_assessments,
                    main,
                    main_evidence,
                    *main_assessments,
                    future_relation,
                    relation_evidence,
                    relation_assessment,
                ],
                artifacts={
                    **main_artifacts,
                    "artifacts/dependency.txt": (
                        dependency_data,
                        "text/plain",
                    ),
                    "artifacts/relation.txt": (relation_data, "text/plain"),
                },
                created_at=NOW,
                primary_claim_record_id=main["record_id"],
            )
            authenticated = [
                *main_assessments,
                *dependency_assessments,
                relation_assessment,
            ]
            evaluation = evaluate_demo(pack_path, authenticated)
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertIn(
                "postdates policy cutoff",
                " ".join(evaluation.dimension_results["dependency-closure"].basis),
            )

    def test_future_policy_cutoff_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            with self.assertRaises(PolicyError):
                evaluate_pack(
                    validate_pack(str(pack_path)),
                    make_policy(),
                    as_of=datetime(2099, 1, 1, tzinfo=timezone.utc),
                )

    def test_claim_after_policy_cutoff_cannot_allow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ordinary = make_claim()
            future_claim = seal_record(
                {
                    **{
                        key: value
                        for key, value in ordinary.items()
                        if key not in {"claim_id", "record_id"}
                    },
                    "issued_at": "2026-07-29T15:00:00+00:00",
                }
            )
            data = b"future claim evidence\n"
            evidence = make_evidence(future_claim, data)
            assessments = [
                make_assessment(
                    future_claim,
                    dimension=dimension,
                    evidence_refs=[evidence["record_id"]],
                )
                for dimension in [
                    "dependency-closure",
                    "known-objections",
                    "statement-precision",
                ]
            ]
            pack_path = write_demo(
                root / "pack",
                claim=future_claim,
                evidence=evidence,
                assessments=assessments,
                artifacts={"artifacts/evidence.txt": (data, "text/plain")},
            )
            self.assertEqual(
                evaluate_demo(pack_path, assessments).decision,
                Decision.UNKNOWN,
            )

    def test_receipt_separates_cutoff_actual_times_and_catalogue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            pack = validate_pack(str(pack_path))
            evaluation = evaluate_demo(pack_path, assessments)
            receipt = create_use_receipt(
                pack,
                claim,
                make_policy(),
                evaluation,
                purpose="timestamp separation test",
            )

            self.assertEqual(receipt["policy_as_of"], AS_OF.isoformat())
            self.assertGreater(receipt["evaluated_at"], receipt["policy_as_of"])
            self.assertGreater(
                receipt["retrieval"]["retrieved_at"],
                receipt["policy_as_of"],
            )
            self.assertEqual(receipt["retrieval"]["catalogue_head"], "")
            self.assertNotEqual(
                receipt["retrieval"]["catalogue_head"],
                pack.package_root,
            )

    def test_receipt_rejects_package_root_as_catalogue_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            pack = validate_pack(str(pack_path))
            evaluation = evaluate_demo(pack_path, assessments)
            with self.assertRaisesRegex(
                ValueError,
                "package root cannot be relabelled",
            ):
                create_use_receipt(
                    pack,
                    claim,
                    make_policy(),
                    evaluation,
                    purpose="identity-category confusion test",
                    catalogue_head=pack.package_root,
                )

            receipt = create_use_receipt(
                pack,
                claim,
                make_policy(),
                evaluation,
                purpose="structural identity-category confusion test",
            )
            receipt["retrieval"]["catalogue_head"] = pack.package_root
            receipt["record_id"] = record_id_for(receipt)
            with self.assertRaisesRegex(
                ValidationError,
                "must not relabel",
            ):
                verify_use_receipt(receipt)

    def test_receipt_and_ledger_paths_cannot_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            shared = Path(temporary) / "shared.json"
            original = pretty_bytes(empty_ledger())
            shared.write_bytes(original)
            with (
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                result = main(
                    [
                        "decide",
                        str(ROOT / "examples/z20"),
                        "--policy",
                        str(ROOT / "policies/cautious-scientific-use-v0.1.json"),
                        "--as-of",
                        "2026-07-29T13:00:00+00:00",
                        "--receipt",
                        str(shared),
                        "--seen-ledger",
                        str(shared),
                        "--update-ledger",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertEqual(shared.read_bytes(), original)

    def test_missing_ledger_requires_explicit_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary) / "seen.json"
            common = [
                "decide",
                str(ROOT / "examples/z20"),
                "--policy",
                str(ROOT / "policies/cautious-scientific-use-v0.1.json"),
                "--as-of",
                "2026-07-29T13:00:00+00:00",
                "--seen-ledger",
                str(ledger),
                "--update-ledger",
            ]
            with (
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                missing_result = main(common)
            self.assertEqual(missing_result, 2)
            self.assertFalse(ledger.exists())

            with (
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                initialized_result = main(common + ["--init-ledger"])
            self.assertEqual(initialized_result, 0)
            self.assertEqual(
                load_ledger(ledger)["schema_version"],
                "claimpack-seen-ledger/0.1",
            )

    def test_correction_prevents_allow_and_propagates_qualification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            correction = make_assessment(
                claim,
                dimension="proof-completeness",
                outcome="unknown",
                stance="neutral",
                assessment_kind="correction",
                issuer_id="corrector:test",
                qualifications=["claim requires a material correction"],
            )
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
                extra_records=[correction],
            )
            evaluation = evaluate_demo(pack_path, assessments)
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertIn(
                "claim requires a material correction",
                evaluation.qualifications,
            )

    def test_withdrawal_qualification_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            objection = make_objection(claim)
            withdrawal = make_withdrawal(claim, objection)
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
                extra_records=[objection, withdrawal],
            )
            evaluation = evaluate_demo(
                pack_path,
                assessments,
                extra_authenticated=[withdrawal["record_id"]],
            )
            self.assertEqual(evaluation.decision, Decision.ALLOW)
            self.assertIn(
                "objection withdrawn by its issuer",
                evaluation.qualifications,
            )

    def test_objection_to_positive_assessment_blocks_support(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            objection = make_objection(assessments[0])
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
                extra_records=[objection],
            )
            evaluation = evaluate_demo(pack_path, assessments)
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertIn(
                objection["record_id"],
                {item["record_id"] for item in evaluation.used_records},
            )
            self.assertIn(
                "retain objection qualification",
                evaluation.qualifications,
            )

    def test_assessment_budget_cannot_downgrade_retraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            retraction = make_assessment(
                claim,
                dimension="proof-completeness",
                outcome="fail",
                stance="challenges",
                assessment_kind="retraction",
                issuer_id="retractor:test",
                qualifications=["claim was explicitly retracted"],
            )
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
                extra_records=[retraction],
            )
            evaluation = evaluate_demo(
                pack_path,
                assessments,
                policy=make_policy(assessment_count="2"),
            )
            self.assertEqual(evaluation.decision, Decision.DENY)
            self.assertEqual(evaluation.termination_reason, "limit")
            self.assertIn("claim was explicitly retracted", evaluation.qualifications)

    def test_all_current_adverse_qualifications_survive_retraction_precedence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            objection = make_objection(claim)
            correction = make_assessment(
                claim,
                dimension="proof-completeness",
                outcome="unknown",
                stance="neutral",
                assessment_kind="correction",
                issuer_id="corrector:test",
                qualifications=["claim requires a material correction"],
            )
            retraction = make_assessment(
                claim,
                dimension="proof-completeness",
                outcome="fail",
                stance="challenges",
                assessment_kind="retraction",
                issuer_id="retractor:test",
                qualifications=["claim was explicitly retracted"],
            )
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
                extra_records=[objection, correction, retraction],
            )
            evaluation = evaluate_demo(pack_path, assessments)
            self.assertEqual(evaluation.decision, Decision.DENY)
            for qualification in [
                "retain objection qualification",
                "claim requires a material correction",
                "claim was explicitly retracted",
            ]:
                self.assertIn(qualification, evaluation.qualifications)

    def test_graph_adverse_qualifications_survive_retraction_precedence(
        self,
    ) -> None:
        for target_kind in ["dependency", "relation"]:
            with (
                self.subTest(target_kind=target_kind),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                dependency = make_claim(
                    natural="Dependency theorem.",
                    aliases=["dependency"],
                )
                dependency_data = b"dependency evidence\n"
                dependency_evidence = make_evidence(
                    dependency,
                    dependency_data,
                    path="artifacts/dependency.txt",
                )
                dependency_assessments = [
                    make_assessment(
                        dependency,
                        dimension=dimension,
                        evidence_refs=[dependency_evidence["record_id"]],
                    )
                    for dimension in ["dependency-closure", "statement-precision"]
                ]
                main, main_evidence, main_assessments, main_artifacts = demo_components(
                    dependency_targets=[
                        {
                            "record_id": dependency["record_id"],
                            "record_type": "claim-version",
                        }
                    ]
                )
                relation = make_relation(main, dependency)
                target = dependency if target_kind == "dependency" else relation
                dimension = (
                    "proof-completeness"
                    if target_kind == "dependency"
                    else "semantic-scope-match"
                )
                objection = make_assessment(
                    target,
                    dimension=dimension,
                    outcome="unknown",
                    stance="challenges",
                    assessment_kind="objection",
                    issuer_id=f"objector:{target_kind}",
                    qualifications=[f"retain {target_kind} objection"],
                    authentication="unverified",
                )
                correction = make_assessment(
                    target,
                    dimension=dimension,
                    outcome="unknown",
                    stance="neutral",
                    assessment_kind="correction",
                    issuer_id=f"corrector:{target_kind}",
                    qualifications=[f"retain {target_kind} correction"],
                )
                retraction = make_assessment(
                    target,
                    dimension=dimension,
                    outcome="fail",
                    stance="challenges",
                    assessment_kind="retraction",
                    issuer_id=f"retractor:{target_kind}",
                    qualifications=[f"retain {target_kind} retraction"],
                )
                pack_path = write_pack(
                    root / "pack",
                    records=[
                        dependency,
                        dependency_evidence,
                        *dependency_assessments,
                        main,
                        main_evidence,
                        *main_assessments,
                        relation,
                        objection,
                        correction,
                        retraction,
                    ],
                    artifacts={
                        **main_artifacts,
                        "artifacts/dependency.txt": (
                            dependency_data,
                            "text/plain",
                        ),
                    },
                    created_at=NOW,
                    primary_claim_record_id=main["record_id"],
                )
                evaluation = evaluate_demo(
                    pack_path,
                    main_assessments + dependency_assessments,
                )
                self.assertEqual(evaluation.decision, Decision.DENY)
                used_ids = {item["record_id"] for item in evaluation.used_records}
                for item, qualification in [
                    (objection, f"retain {target_kind} objection"),
                    (correction, f"retain {target_kind} correction"),
                    (retraction, f"retain {target_kind} retraction"),
                ]:
                    self.assertIn(item["record_id"], used_ids)
                    self.assertIn(qualification, evaluation.qualifications)

    def test_empty_dependency_declaration_needs_positive_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            claim = make_claim()
            pack_path = write_pack(
                Path(temporary) / "pack",
                records=[claim],
                created_at=NOW,
                primary_claim_record_id=claim["record_id"],
            )
            policy = make_policy()
            policy["dimensions"] = {
                "dependency-closure": policy["dimensions"]["dependency-closure"]
            }
            policy["policy_digest"] = policy_digest_for(policy)
            evaluation = evaluate_pack(
                validate_pack(str(pack_path)),
                policy,
                as_of=AS_OF,
                objection_search_complete=True,
                objection_search_context="bounded synthetic snapshot",
            )
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertEqual(
                evaluation.dimension_results["dependency-closure"].result,
                "unknown",
            )

    def test_embedded_evidence_policy_cannot_make_evidence_optional(self) -> None:
        policy = make_policy()
        policy["require_evidence_for_positive"] = False
        policy["policy_digest"] = policy_digest_for(policy)
        with tempfile.TemporaryDirectory() as temporary:
            claim = make_claim()
            pack_path = write_pack(
                Path(temporary) / "pack",
                records=[claim],
                created_at=NOW,
                primary_claim_record_id=claim["record_id"],
            )
            with self.assertRaises(ValidationError):
                evaluate_pack(
                    validate_pack(str(pack_path)),
                    policy,
                    as_of=AS_OF,
                )

    def test_external_authentication_is_authoritative_over_package_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = make_claim()
            data = b"externally authenticated evidence\n"
            evidence = make_evidence(claim, data)
            assessments = [
                make_assessment(
                    claim,
                    dimension=dimension,
                    evidence_refs=[evidence["record_id"]],
                    authentication="unverified",
                )
                for dimension in [
                    "dependency-closure",
                    "known-objections",
                    "statement-precision",
                ]
            ]
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts={"artifacts/evidence.txt": (data, "text/plain")},
            )
            self.assertEqual(
                evaluate_demo(pack_path, assessments).decision,
                Decision.ALLOW,
            )

    def test_corrupt_zip_member_is_typed_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            directory = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            archive = root / "pack.zip"
            with zipfile.ZipFile(
                archive,
                "w",
                compression=zipfile.ZIP_STORED,
            ) as handle:
                for path in sorted(directory.rglob("*")):
                    if path.is_file():
                        handle.write(path, path.relative_to(directory).as_posix())

            with zipfile.ZipFile(archive) as handle:
                info = handle.getinfo("artifacts/evidence.txt")
            raw = bytearray(archive.read_bytes())
            name_length = int.from_bytes(
                raw[info.header_offset + 26 : info.header_offset + 28],
                "little",
            )
            extra_length = int.from_bytes(
                raw[info.header_offset + 28 : info.header_offset + 30],
                "little",
            )
            data_offset = info.header_offset + 30 + name_length + extra_length
            raw[data_offset] ^= 0x01
            archive.write_bytes(raw)

            with self.assertRaises(ValidationError):
                validate_pack(str(archive))
            with (
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(main(["validate", str(archive)]), 2)

    def test_extreme_timestamp_is_rejected_structurally(self) -> None:
        claim = make_claim()
        with self.assertRaises(ValidationError):
            seal_record(
                {
                    **{
                        key: value
                        for key, value in claim.items()
                        if key not in {"claim_id", "record_id"}
                    },
                    "issued_at": "0001-01-01T00:00:00+14:00",
                }
            )

    def test_malformed_catalog_and_ledger_are_typed_failures(self) -> None:
        catalog = strict_loads((ROOT / "catalog/catalog.json").read_bytes())
        catalog["entries"][0]["claim_record_id"] = []
        catalog["catalog_head"] = ni_sha256(b"irrelevant")
        with self.assertRaises(ValidationError):
            validate_catalog(catalog)

        with tempfile.TemporaryDirectory() as temporary:
            ledger_path = Path(temporary) / "ledger.json"
            ledger_path.write_bytes(
                pretty_bytes(
                    {
                        "adverse_records": {"x": []},
                        "schema_version": "claimpack-seen-ledger/0.1",
                        "updated_at": NOW,
                    }
                )
            )
            with self.assertRaises(ValidationError):
                load_ledger(ledger_path)

    def test_directory_member_swap_to_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            directory = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            outside = root / "outside.txt"
            outside.write_bytes(b"synthetic evidence\n")
            artifact = directory / "artifacts/evidence.txt"

            with PackReader(directory) as reader:
                reader.list_files()
                artifact.unlink()
                artifact.symlink_to(outside)
                with self.assertRaises(ValidationError):
                    reader.read_bytes("artifacts/evidence.txt")


if __name__ == "__main__":
    unittest.main()

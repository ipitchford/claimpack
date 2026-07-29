from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from claimpack.build import write_pack
from claimpack.errors import PolicyError, ValidationError
from claimpack.ledger import load_ledger
from claimpack.policy import Decision, evaluate_pack
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


AS_OF = datetime(2026, 7, 29, 14, 0, tzinfo=timezone.utc)


def evaluate_demo(
    pack_path: Path,
    assessments: list[dict],
    *,
    policy: dict | None = None,
    ledger_records: list[dict] | None = None,
    extra_authenticated: list[str] | None = None,
):
    authenticated = {
        item["record_id"]
        for item in assessments
        if item["authentication"]["status"] == "claimed-verified"
        and item["outcome"] == "pass"
    }
    authenticated.update(extra_authenticated or [])
    return evaluate_pack(
        validate_pack(str(pack_path)),
        policy or make_policy(),
        as_of=AS_OF,
        ledger_records=ledger_records,
        objection_search_complete=True,
        objection_search_context="synthetic complete fixture snapshot",
        authenticated_record_ids=authenticated,
        authentication_context="synthetic test trust root",
    )


class PolicyTests(unittest.TestCase):
    def test_consumer_authenticated_embedded_evidence_can_allow(self) -> None:
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
            evaluation = evaluate_demo(pack_path, assessments)
            self.assertEqual(evaluation.decision, Decision.ALLOW)
            receipt = create_use_receipt(
                validate_pack(str(pack_path)),
                claim,
                make_policy(),
                evaluation,
                purpose="synthetic downstream use",
            )
            verify_use_receipt(receipt)
            self.assertEqual(receipt["decision"], "ALLOW")
            self.assertIn("retain root condition", receipt["qualifications"])
            self.assertIn("retain evidence limitation", receipt["qualifications"])
            self.assertIn("retain assessment qualification", receipt["qualifications"])

    def test_package_self_authentication_does_not_allow(self) -> None:
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
            evaluation = evaluate_pack(
                validate_pack(str(pack_path)),
                make_policy(),
                as_of=AS_OF,
                objection_search_complete=True,
                objection_search_context="synthetic complete fixture snapshot",
            )
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)

    def test_authentication_requires_context(self) -> None:
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
                    as_of=AS_OF,
                    authenticated_record_ids={assessments[0]["record_id"]},
                )

    def test_open_and_stale_objections_remain_unknown(self) -> None:
        for issued_at in [NOW, "2020-01-01T00:00:00+00:00"]:
            with (
                self.subTest(issued_at=issued_at),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                claim, evidence, assessments, artifacts = demo_components()
                objection = make_objection(claim, issued_at=issued_at)
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
                    evaluation.dimension_results["known-objections"].assessment_refs,
                )

    def test_authenticated_same_issuer_withdrawal_resolves_objection(self) -> None:
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
                withdrawal["record_id"],
                {item["record_id"] for item in evaluation.used_records},
            )

    def test_version_washing_does_not_drop_old_objection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old_claim, _, _, _ = demo_components()
            objection = make_objection(old_claim)
            new_claim = make_claim(
                aliases=["repackaged test theorem"],
                lineage=[
                    {
                        "record_id": old_claim["record_id"],
                        "relation": "revises",
                    }
                ],
            )
            self.assertEqual(old_claim["claim_id"], new_claim["claim_id"])
            self.assertNotEqual(old_claim["record_id"], new_claim["record_id"])
            data = b"new package, same exact claim\n"
            evidence = make_evidence(new_claim, data)
            assessments = [
                make_assessment(
                    new_claim,
                    dimension=dimension,
                    evidence_refs=[evidence["record_id"]],
                )
                for dimension in ["known-objections", "statement-precision"]
            ]
            pack_path = write_demo(
                root / "pack",
                claim=new_claim,
                evidence=evidence,
                assessments=assessments,
                artifacts={"artifacts/evidence.txt": (data, "text/plain")},
            )
            evaluation = evaluate_demo(
                pack_path,
                assessments,
                ledger_records=[objection],
            )
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)

    def test_objection_to_supporting_evidence_blocks_allow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            evidence_objection = make_objection(evidence)
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
                extra_records=[evidence_objection],
            )
            evaluation = evaluate_demo(pack_path, assessments)
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertIn(
                evidence_objection["record_id"],
                {item["record_id"] for item in evaluation.used_records},
            )

    def test_external_only_evidence_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components(embedded=False)
            pack_path = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            self.assertEqual(
                evaluate_demo(pack_path, assessments).decision,
                Decision.UNKNOWN,
            )

    def test_assessment_budget_exhaustion_is_bounded_unknown(self) -> None:
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
            evaluation = evaluate_demo(
                pack_path,
                assessments,
                policy=make_policy(assessment_count="1"),
            )
            self.assertEqual(evaluation.decision, Decision.UNKNOWN)
            self.assertEqual(evaluation.termination_reason, "limit")
            self.assertIn("assessment_count", evaluation.limits_hit)

    def test_dependency_qualifications_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency = make_claim(
                natural="Dependency theorem.",
                aliases=["dependency"],
                conditions=["retain dependency condition"],
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
                    qualifications=["retain dependency assessment qualification"],
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
            relation = make_relation(
                main,
                dependency,
                limitations=["retain relation limitation"],
            )
            relation_data = b"relation alignment evidence\n"
            relation_evidence = make_evidence(
                relation,
                relation_data,
                path="artifacts/relation.txt",
            )
            relation_assessment = make_assessment(
                relation,
                dimension="semantic-scope-match",
                assessment_kind="correspondence",
                evidence_refs=[relation_evidence["record_id"]],
                qualifications=["retain relation assessment qualification"],
            )
            records = [
                dependency,
                dependency_evidence,
                *dependency_assessments,
                main,
                main_evidence,
                *main_assessments,
                relation,
                relation_evidence,
                relation_assessment,
            ]
            artifacts = {
                **main_artifacts,
                "artifacts/dependency.txt": (dependency_data, "text/plain"),
                "artifacts/relation.txt": (relation_data, "text/plain"),
            }
            pack_path = write_pack(
                root / "pack",
                records=records,
                artifacts=artifacts,
                created_at=NOW,
                primary_claim_record_id=main["record_id"],
            )
            authenticated = main_assessments + [
                *dependency_assessments,
                relation_assessment,
            ]
            evaluation = evaluate_demo(pack_path, authenticated)
            self.assertEqual(evaluation.decision, Decision.ALLOW)
            for qualification in {
                "retain dependency condition",
                "retain relation limitation",
                "retain dependency assessment qualification",
                "retain relation assessment qualification",
            }:
                self.assertIn(qualification, evaluation.qualifications)

    def test_receipt_subject_cannot_be_swapped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            other = make_claim(natural="A different exact statement.")
            pack_path = write_pack(
                root / "pack",
                records=[claim, other, evidence, *assessments],
                artifacts=artifacts,
                created_at=NOW,
                primary_claim_record_id=claim["record_id"],
            )
            pack = validate_pack(str(pack_path))
            evaluation = evaluate_demo(pack_path, assessments)
            with self.assertRaises(ValueError):
                create_use_receipt(
                    pack,
                    other,
                    make_policy(),
                    evaluation,
                    purpose="confused deputy test",
                )

    def test_positive_record_cannot_be_loaded_as_adverse_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ledger.json"
            claim, evidence, assessments, _ = demo_components()
            positive = assessments[0]
            from claimpack.canonical import pretty_bytes

            path.write_bytes(
                pretty_bytes(
                    {
                        "adverse_records": {positive["record_id"]: positive},
                        "schema_version": "claimpack-seen-ledger/0.1",
                        "updated_at": NOW,
                    }
                )
            )
            with self.assertRaises(ValidationError):
                load_ledger(path)


if __name__ == "__main__":
    unittest.main()

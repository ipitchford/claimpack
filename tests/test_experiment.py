from __future__ import annotations

import io
import inspect
import tarfile
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from claimpack.canonical import canonical_bytes, strict_loads
from claimpack.errors import ParseError, ValidationError
from claimpack.experiment import (
    ANSWER_VERSION,
    PLAN_VERSION,
    RANDOMIZATION_ALGORITHM,
    _extract_base_archive,
    audit_study_completeness,
    build_participant_bundle,
    bundle_manifest,
    make_run_receipt,
    materialize_allocated_bundles,
    prepare_plan,
    score_trial_answer,
    validate_allocation,
    validate_bundle_commitment,
    validate_case,
    validate_plan,
    validate_run_receipt,
    validate_score,
    validate_trial_answer,
)
from claimpack.ids import ni_sha256, sha256_label

ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "evaluation/cases/C001-vr2-k4/case.json"
PROVIDER_V3_CASE_PATH = ROOT / "evaluation/cases/C001-vr2-k4/case-provider-v3.json"
GOLD_PATH = ROOT / "evaluation/cases/C001-vr2-k4/gold.json"
SCORED_AT = "2026-07-29T15:00:00+00:00"
STARTED_AT = "2026-07-29T14:58:00+00:00"
FINISHED_AT = "2026-07-29T14:59:00+00:00"
SCORER_IDENTITY = "claimpack-reference-scorer"
SCORER_VERSION = "0.1-test"


def _load(path: Path) -> dict[str, object]:
    value = strict_loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


def _plan_template(case: dict[str, object], *, trial_count: int = 4) -> dict:
    case_sha = sha256_label(CASE_PATH.read_bytes())
    return {
        "analysis": {
            "comparative_claim_allowed": False,
            "failed_runs_retained": True,
            "gold_decisions": ["UNKNOWN"],
            "missing_pairs_fail": True,
            "no_aggregate_score": True,
        },
        "budgets": {
            "context": "matched",
            "time": "matched",
            "tools": "matched",
        },
        "case_digests": [
            {
                "case_id": case["case_id"],
                "case_sha256": case_sha,
                "gold_sha256": case["gold_sha256"],
            }
        ],
        "created_at": "2026-07-29T14:00:00+00:00",
        "endpoints": [
            "statement precision",
            "version identity",
            "scope calibration",
            "unsafe observed actions",
        ],
        "estimand": "whole-package workflow utility",
        "exclusion_rules": [
            "retain failures",
            "retain timeouts",
            "link retries rather than replacing outcomes",
        ],
        "hypothesis_mask": "Participants receive no arm label or expected answer.",
        "model_policy": {
            "context": "fresh",
            "model": "same within block",
            "tools": "same within block",
        },
        "plan_id": "",
        "prohibited_actions": [
            "network access",
            "reading outside the bundle",
            "executing package code",
        ],
        "randomization": {
            "algorithm": RANDOMIZATION_ALGORITHM,
            "seed_commitment": "",
        },
        "scheduled_trials": [
            {
                "case_id": case["case_id"],
                "replicate": str(index + 1),
                "trial_id": "",
            }
            for index in range(trial_count)
        ],
        "schema_version": PLAN_VERSION,
        "status": "developmental-smoke-preregistered",
        "study_id": "claimpack-cold-agent-smoke-2026-07-29",
        "terminology": "randomized, hypothesis-masked, scorer-masked",
    }


def _answer_from_gold(gold: dict, trial_id: str) -> dict:
    dependency = gold["dependency"]
    return {
        "actions": {
            "commands": [],
            "files_outside_bundle_read": False,
            "network_used": False,
            "package_code_executed": False,
            "replay_executed": False,
        },
        "assurance": deepcopy(gold["assurance"]),
        "claim": deepcopy(gold["claim"]),
        "decision": {
            "reasons": deepcopy(gold["required_decision_reasons"]),
            "value": gold["decision"],
        },
        "dependencies": [
            {
                "code": dependency["code"],
                "limitations": deepcopy(dependency["mandatory_limitations"]),
                "load_bearing_for": dependency["load_bearing_for"],
                "semantic_alignment": dependency["semantic_alignment"],
                "statement": dependency["statement"],
            }
        ],
        "downstream": {
            "qualification_codes": deepcopy(gold["mandatory_qualification_codes"]),
            "statement": gold["downstream_statement"],
            "use": gold["downstream_use"],
        },
        "notes": "",
        "objections": deepcopy(gold["objections"]),
        "schema_version": ANSWER_VERSION,
        "scope": deepcopy(gold["scope"]),
        "trial_id": trial_id,
        "unavailable_sources": deepcopy(gold["unavailable_source_codes"]),
        "version": deepcopy(gold["version"]),
    }


def _score(
    answer: dict,
    gold: dict,
    *,
    plan_id: str | None = None,
    case: dict | None = None,
    observed_actions: list[str] | None = None,
    scorer_identity: str = SCORER_IDENTITY,
    scorer_version: str = SCORER_VERSION,
) -> dict:
    """Call both the pre-hardening and intended bound scorer APIs.

    Signature introspection keeps unrelated regression tests useful while the
    new receipt fields are being implemented. The binding tests below still
    require those fields unconditionally.
    """

    case = case or _load(CASE_PATH)
    plan_id = plan_id or ni_sha256(b"unit-test-plan")
    observed_actions = observed_actions or []
    kwargs = {
        "answer_sha256": sha256_label(canonical_bytes(answer)),
        "observed_actions": observed_actions,
        "scored_at": SCORED_AT,
    }
    supported = inspect.signature(score_trial_answer).parameters
    proposed = {
        "case_id": case["case_id"],
        "case_sha256": (
            sha256_label(CASE_PATH.read_bytes())
            if case == _load(CASE_PATH)
            else sha256_label(canonical_bytes(case))
        ),
        "gold_sha256": case["gold_sha256"],
        "plan_id": plan_id,
        "scorer_identity": scorer_identity,
        "scorer_version": scorer_version,
    }
    kwargs.update({key: value for key, value in proposed.items() if key in supported})
    return score_trial_answer(answer, gold, **kwargs)


def _run(
    plan_id: str,
    trial_id: str,
    *,
    answer_sha256: str,
    termination: str = "completed",
) -> dict:
    return make_run_receipt(
        plan_id=plan_id,
        trial_id=trial_id,
        bundle_id=ni_sha256(f"bundle:{trial_id}".encode()),
        answer_sha256=answer_sha256,
        trace_sha256=sha256_label(f"trace:{trial_id}".encode()),
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
        model="cold-agent-test-fixture",
        termination=termination,
        observed_actions=[],
        notes=[],
    )


def _relative_file_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class ExperimentFixtureTests(unittest.TestCase):
    """AB01, AB03, AB04, AB09, AB11, and AB18 fixture invariants."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.case = _load(CASE_PATH)
        cls.gold = _load(GOLD_PATH)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temporary.name)
        cls.ordinary = cls.work / "trial-ordinary"
        cls.claimpack = cls.work / "trial-claimpack"
        cls.ordinary_bundle = build_participant_bundle(
            ROOT,
            cls.case,
            condition="ordinary-release",
            trial_id="trial-0000000000000001",
            destination=cls.ordinary,
        )
        cls.claimpack_bundle = build_participant_bundle(
            ROOT,
            cls.case,
            condition="ordinary-plus-claimpack",
            trial_id="trial-0000000000000002",
            destination=cls.claimpack,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_ab01_bundles_exclude_oracles_and_arm_labels(self) -> None:
        forbidden_path_parts = {
            ".git",
            "case.json",
            "gold.json",
            "tests",
        }
        for bundle_root in (self.ordinary, self.claimpack):
            relative_paths = {
                path.relative_to(bundle_root).as_posix()
                for path in bundle_root.rglob("*")
            }
            for relative in relative_paths:
                self.assertTrue(
                    forbidden_path_parts.isdisjoint(Path(relative).parts),
                    relative,
                )

            descriptor = _load(bundle_root / "BUNDLE.json")
            self.assertEqual(
                set(descriptor),
                {"bundle_id", "files", "schema_version", "trial_id"},
            )
            serialized = canonical_bytes(descriptor)
            self.assertNotIn(b"ordinary-release", serialized)
            self.assertNotIn(b"ordinary-plus-claimpack", serialized)
            self.assertNotIn(b"gold_sha256", serialized)
            self.assertNotIn(b"case_id", serialized)

    def test_ab01_manifest_exactly_describes_materialized_files(self) -> None:
        for root, returned in (
            (self.ordinary, self.ordinary_bundle),
            (self.claimpack, self.claimpack_bundle),
        ):
            descriptor = _load(root / "BUNDLE.json")
            self.assertEqual(descriptor, returned)
            self.assertEqual(descriptor["files"], bundle_manifest(root))

    def test_ab01_provider_schema_binds_exact_trial_id_in_bundle(self) -> None:
        case = _load(PROVIDER_V3_CASE_PATH)
        trial_id = "trial-0123456789abcdef"
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / trial_id
            returned = build_participant_bundle(
                ROOT,
                case,
                condition="ordinary-release",
                trial_id=trial_id,
                destination=destination,
            )
            schema = _load(destination / "RESPONSE_SCHEMA.json")
            self.assertEqual(
                schema["properties"]["trial_id"],
                {"const": trial_id, "type": "string"},
            )
            self.assertEqual(returned["files"], bundle_manifest(destination))
            descriptor = _load(destination / "BUNDLE.json")
            self.assertEqual(descriptor, returned)

    def test_ab03_base_and_common_materials_are_byte_identical(self) -> None:
        ordinary_files = _relative_file_bytes(self.ordinary)
        claimpack_files = _relative_file_bytes(self.claimpack)
        shared = set(ordinary_files) & set(claimpack_files)
        shared.discard("BUNDLE.json")
        self.assertTrue(shared)
        for relative in sorted(shared):
            self.assertEqual(
                ordinary_files[relative],
                claimpack_files[relative],
                relative,
            )
        self.assertEqual(
            {
                path: data
                for path, data in ordinary_files.items()
                if path.startswith("MATERIALS/release/")
            },
            {
                path: data
                for path, data in claimpack_files.items()
                if path.startswith("MATERIALS/release/")
            },
        )
        self.assertEqual(
            set(claimpack_files) - set(ordinary_files),
            {entry["destination"] for entry in self.case["overlay_files"]},
        )

    def test_ab04_every_fact_bearing_overlay_has_base_provenance(self) -> None:
        validate_case(self.case)
        covered = {
            item["overlay_path"]: item["base_sources"]
            for item in self.case["overlay_provenance"]
        }
        fact_bearing = {
            item["destination"]
            for item in self.case["overlay_files"]
            if "/records/" in item["destination"]
            and item["destination"].endswith(".json")
        }
        self.assertTrue(fact_bearing)
        self.assertTrue(fact_bearing.issubset(covered))
        ordinary_paths = set(_relative_file_bytes(self.ordinary))
        for overlay_path in fact_bearing:
            self.assertTrue(covered[overlay_path])
            self.assertTrue(set(covered[overlay_path]).issubset(ordinary_paths))

    def test_ab04_overlay_is_additive_and_allowlisted(self) -> None:
        allowed_exact = {
            "MATERIALS/supplement/CONSUMER_SKILL.md",
            "MATERIALS/supplement/CAUTIOUS_POLICY.json",
            "MATERIALS/supplement/STATIC_CATALOG.json",
            "MATERIALS/supplement/claimpack/claimpack.json",
        }
        for entry in self.case["overlay_files"]:
            destination = entry["destination"]
            self.assertTrue(
                destination in allowed_exact
                or destination.startswith("MATERIALS/supplement/claimpack/records/"),
                destination,
            )
            self.assertNotIn(
                destination, {item["destination"] for item in self.case["common_files"]}
            )

    def test_ab04_missing_record_provenance_fails_closed(self) -> None:
        tampered = deepcopy(self.case)
        record = next(
            item["destination"]
            for item in tampered["overlay_files"]
            if "/records/" in item["destination"]
        )
        tampered["overlay_provenance"] = [
            item
            for item in tampered["overlay_provenance"]
            if item["overlay_path"] != record
        ]
        with self.assertRaises(ValidationError):
            validate_case(tampered)

    def test_ab09_answer_contract_is_closed_and_enum_constrained(self) -> None:
        answer = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        validate_trial_answer(
            answer,
            trial_id="trial-0000000000000001",
        )

        unknown = deepcopy(answer)
        unknown["condition"] = "ordinary-plus-claimpack"
        with self.assertRaises(ValidationError):
            validate_trial_answer(unknown)

        invalid_enum = deepcopy(answer)
        invalid_enum["decision"]["value"] = "MAYBE"
        with self.assertRaises(ValidationError):
            validate_trial_answer(invalid_enum)

        with self.assertRaises(ValidationError):
            validate_trial_answer(answer, trial_id="trial-wrong")

    def test_ab09_duplicate_json_keys_are_rejected_before_validation(self) -> None:
        with self.assertRaises(ParseError):
            strict_loads(
                b'{"schema_version":"claimpack-trial-answer/0.1",'
                b'"trial_id":"trial-a","trial_id":"trial-b"}'
            )

    def test_ab09_python_validator_enforces_shipped_schema_constraints(
        self,
    ) -> None:
        baseline = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        validate_trial_answer(baseline)
        mutations = {}

        invalid_trial_id = deepcopy(baseline)
        invalid_trial_id["trial_id"] = "trial-not-hex"
        mutations["trial_id pattern"] = invalid_trial_id

        invalid_archive = deepcopy(baseline)
        invalid_archive["version"]["archive_sha256"] = "g" * 64
        mutations["archive digest pattern"] = invalid_archive

        invalid_doi = deepcopy(baseline)
        invalid_doi["version"]["doi"] = "not-a-doi"
        mutations["DOI pattern"] = invalid_doi

        invalid_commit = deepcopy(baseline)
        invalid_commit["version"]["git_commit"] = "b" * 39
        mutations["Git commit pattern"] = invalid_commit

        empty_reasons = deepcopy(baseline)
        empty_reasons["decision"]["reasons"] = []
        mutations["decision reasons minItems"] = empty_reasons

        invalid_reason = deepcopy(baseline)
        invalid_reason["decision"]["reasons"] = ["free-form unsupported reason"]
        mutations["decision reason enum"] = invalid_reason

        duplicate_dependency = deepcopy(baseline)
        duplicate_dependency["dependencies"].append(
            deepcopy(duplicate_dependency["dependencies"][0])
        )
        mutations["unique dependency codes"] = duplicate_dependency

        invalid_qualification = deepcopy(baseline)
        invalid_qualification["downstream"]["qualification_codes"] = [
            "invented-qualification"
        ]
        mutations["qualification enum"] = invalid_qualification

        invalid_unavailable = deepcopy(baseline)
        invalid_unavailable["unavailable_sources"] = ["invented-source-code"]
        mutations["unavailable-source enum"] = invalid_unavailable

        for label, answer in mutations.items():
            with self.subTest(label=label):
                with self.assertRaises(ValidationError):
                    validate_trial_answer(answer)

    def test_ab11_scoring_is_arm_neutral_and_uses_no_claimpack_ids(self) -> None:
        answer = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        first = _score(answer, self.gold)
        second = _score(deepcopy(answer), self.gold)
        self.assertEqual(first["metrics"], second["metrics"])
        self.assertNotIn("condition", first)
        self.assertNotIn("bundle_id", first)
        self.assertNotIn(b"ni:///sha-256;", canonical_bytes(self.gold))
        self.assertEqual(
            first["metrics"]["immutable_version"]["actual"],
            self.gold["version"],
        )
        self.assertEqual(
            first["metrics"]["immutable_version"]["result"],
            "pass",
        )

    def test_ab11_score_binds_frozen_context_and_scorer(self) -> None:
        plan_id = ni_sha256(b"sealed plan for binding test")
        answer = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        score = _score(
            answer,
            self.gold,
            plan_id=plan_id,
            case=self.case,
        )
        expected = {
            "case_id": self.case["case_id"],
            "case_sha256": sha256_label(CASE_PATH.read_bytes()),
            "gold_sha256": self.case["gold_sha256"],
            "observed_actions": [],
            "plan_id": plan_id,
            "scorer_identity": SCORER_IDENTITY,
            "scorer_version": SCORER_VERSION,
        }
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(score.get(field), value)
        validate_score(score)

    def test_ab11_self_reported_unsafe_action_cannot_pass_safety(self) -> None:
        answer = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        answer["actions"]["network_used"] = True
        score = _score(answer, self.gold, case=self.case)
        safety_metrics = [
            metric
            for name, metric in score["metrics"].items()
            if "unsafe" in name or "safety" in name
        ]
        self.assertTrue(safety_metrics)
        self.assertTrue(
            any(metric["result"] == "fail" for metric in safety_metrics),
            "self-reported network use must make at least one safety metric fail",
        )

    def test_ab11_unpinned_semantic_text_is_scored_or_review_required(
        self,
    ) -> None:
        mutations = {}

        dependency_statement = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        dependency_statement["dependencies"][0]["statement"] = (
            "A different dependency statement."
        )
        mutations["dependency_statement"] = dependency_statement

        dependency_limitations = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        dependency_limitations["dependencies"][0]["limitations"] = [
            "A materially different limitation."
        ]
        mutations["dependency_limitations"] = dependency_limitations

        decision_reasons = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        decision_reasons["decision"]["reasons"] = ["complete-objection-search-absent"]
        mutations["decision_reasons"] = decision_reasons

        downstream_statement = _answer_from_gold(
            self.gold,
            "trial-0000000000000001",
        )
        downstream_statement["downstream"]["statement"] = (
            "A materially different downstream-use statement."
        )
        mutations["downstream_statement"] = downstream_statement

        for metric_name, answer in mutations.items():
            with self.subTest(metric=metric_name):
                score = _score(answer, self.gold, case=self.case)
                self.assertIn(metric_name, score["metrics"])
                metric = score["metrics"][metric_name]
                self.assertTrue(
                    metric["result"] == "fail"
                    or (
                        metric["result"] in {"unknown", "not-applicable"}
                        and metric.get("review_required") is True
                    ),
                    f"{metric_name} was silently treated as correct",
                )

    def test_ab18_score_has_no_total_or_aggregate(self) -> None:
        score = _score(
            _answer_from_gold(
                self.gold,
                "trial-0000000000000001",
            ),
            self.gold,
        )
        self.assertIs(score["no_aggregate_score"], True)
        self.assertNotIn("total", score)
        self.assertNotIn("aggregate", score)
        self.assertNotIn("overall", score)
        self.assertNotIn("percentage", score)
        validate_score(score)


class ExperimentPlanAndReceiptTests(unittest.TestCase):
    """AB12-AB16 randomization, completeness, and receipt-chain checks."""

    def setUp(self) -> None:
        self.case = _load(CASE_PATH)
        self.gold = _load(GOLD_PATH)
        self.seed = "42" * 32
        self.plan, self.allocation = prepare_plan(
            _plan_template(self.case),
            seed_hex=self.seed,
        )

    def _complete_outcomes(
        self,
        *,
        termination_by_trial: dict[str, str] | None = None,
    ) -> tuple[list[dict], list[dict]]:
        termination_by_trial = termination_by_trial or {}
        runs = []
        scores = []
        for trial in self.plan["scheduled_trials"]:
            answer = _answer_from_gold(self.gold, trial["trial_id"])
            score = _score(
                answer,
                self.gold,
                plan_id=self.plan["plan_id"],
                case=self.case,
            )
            scores.append(score)
            runs.append(
                _run(
                    self.plan["plan_id"],
                    trial["trial_id"],
                    answer_sha256=score["answer_sha256"],
                    termination=termination_by_trial.get(
                        trial["trial_id"],
                        "completed",
                    ),
                )
            )
        return runs, scores

    def test_plan_commitment_is_deterministic_balanced_and_unlabelled(self) -> None:
        repeated_plan, repeated_allocation = prepare_plan(
            _plan_template(self.case),
            seed_hex=self.seed,
        )
        self.assertEqual(self.plan, repeated_plan)
        self.assertEqual(self.allocation, repeated_allocation)
        self.assertEqual(
            self.plan["randomization"]["seed_commitment"],
            sha256_label(bytes.fromhex(self.seed)),
        )
        counts = {
            condition: sum(
                item["condition"] == condition
                for item in self.allocation["assignments"]
            )
            for condition in {
                "ordinary-release",
                "ordinary-plus-claimpack",
            }
        }
        self.assertLessEqual(
            abs(counts["ordinary-release"] - counts["ordinary-plus-claimpack"]), 1
        )
        for trial in self.plan["scheduled_trials"]:
            self.assertRegex(trial["trial_id"], r"^trial-[0-9a-f]{16}$")
            self.assertNotIn(trial["case_id"], trial["trial_id"])
        validate_plan(self.plan)
        validate_allocation(self.allocation, self.plan)

    def test_plan_seed_substitution_and_unbalanced_allocation_fail(self) -> None:
        substituted = deepcopy(self.allocation)
        substituted["seed"] = "00" * 32
        with self.assertRaises(ValidationError):
            validate_allocation(substituted, self.plan)

        unbalanced = deepcopy(self.allocation)
        for assignment in unbalanced["assignments"]:
            assignment["condition"] = "ordinary-release"
        with self.assertRaises(ValidationError):
            validate_allocation(unbalanced, self.plan)

        balanced_swap = deepcopy(self.allocation)
        first = next(
            index
            for index, item in enumerate(balanced_swap["assignments"])
            if item["condition"] == "ordinary-release"
        )
        second = next(
            index
            for index, item in enumerate(balanced_swap["assignments"])
            if item["condition"] == "ordinary-plus-claimpack"
        )
        balanced_swap["assignments"][first]["condition"] = "ordinary-plus-claimpack"
        balanced_swap["assignments"][second]["condition"] = "ordinary-release"
        projection = deepcopy(balanced_swap)
        projection.pop("allocation_id")
        balanced_swap["allocation_id"] = ni_sha256(canonical_bytes(projection))
        with self.assertRaises(ValidationError):
            validate_allocation(balanced_swap, self.plan)

    def test_allocated_bundle_commitment_binds_every_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            commitment = materialize_allocated_bundles(
                ROOT,
                self.plan,
                self.allocation,
                self.case,
                case_sha256=sha256_label(CASE_PATH.read_bytes()),
                destination_root=Path(temporary) / "bundles",
            )
            validate_bundle_commitment(commitment, self.plan)
            committed = {
                item["trial_id"]: item["bundle_id"] for item in commitment["entries"]
            }
            runs, scores = self._complete_outcomes()
            rebound_runs = []
            for run in runs:
                rebound_runs.append(
                    make_run_receipt(
                        plan_id=run["plan_id"],
                        trial_id=run["trial_id"],
                        bundle_id=committed[run["trial_id"]],
                        answer_sha256=run["answer_sha256"],
                        trace_sha256=run["trace_sha256"],
                        started_at=run["started_at"],
                        finished_at=run["finished_at"],
                        model=run["model"],
                        termination=run["termination"],
                        observed_actions=run["observed_actions"],
                        notes=run["notes"],
                    )
                )
            audit = audit_study_completeness(
                self.plan,
                self.allocation,
                rebound_runs,
                scores,
                bundle_commitment=commitment,
            )
            self.assertIs(audit["bundle_binding_verified"], True)

            first_run = rebound_runs[0]
            other_bundle = next(
                bundle_id
                for trial_id, bundle_id in committed.items()
                if trial_id != first_run["trial_id"]
            )
            rebound_runs[0] = make_run_receipt(
                plan_id=first_run["plan_id"],
                trial_id=first_run["trial_id"],
                bundle_id=other_bundle,
                answer_sha256=first_run["answer_sha256"],
                trace_sha256=first_run["trace_sha256"],
                started_at=first_run["started_at"],
                finished_at=first_run["finished_at"],
                model=first_run["model"],
                termination=first_run["termination"],
                observed_actions=first_run["observed_actions"],
                notes=first_run["notes"],
            )
            with self.assertRaises(ValidationError):
                audit_study_completeness(
                    self.plan,
                    self.allocation,
                    rebound_runs,
                    scores,
                    bundle_commitment=commitment,
                )

    def test_ab12_single_unknown_case_disables_comparative_claim(self) -> None:
        runs, scores = self._complete_outcomes()
        audit = audit_study_completeness(
            self.plan,
            self.allocation,
            runs,
            scores,
        )
        self.assertTrue(audit["complete"])
        self.assertFalse(audit["always_unknown_baseline_exposed"])
        self.assertFalse(audit["comparative_claim_allowed"])

    def test_ab13_missing_extra_and_duplicate_outcomes_fail_closed(self) -> None:
        runs, scores = self._complete_outcomes()
        missing = audit_study_completeness(
            self.plan,
            self.allocation,
            runs[:-1],
            scores[:-1],
        )
        self.assertFalse(missing["complete"])
        self.assertEqual(len(missing["missing_runs"]), 1)
        self.assertEqual(len(missing["missing_scores"]), 1)

        with self.assertRaises(ValidationError):
            audit_study_completeness(
                self.plan,
                self.allocation,
                runs + [deepcopy(runs[0])],
                scores,
            )
        with self.assertRaises(ValidationError):
            audit_study_completeness(
                self.plan,
                self.allocation,
                runs,
                scores + [deepcopy(scores[0])],
            )

        extra_answer = _answer_from_gold(
            self.gold,
            "trial-ffffffffffffffff",
        )
        extra_score = _score(
            extra_answer,
            self.gold,
            plan_id=self.plan["plan_id"],
            case=self.case,
        )
        extra_run = _run(
            self.plan["plan_id"],
            "trial-ffffffffffffffff",
            answer_sha256=extra_score["answer_sha256"],
        )
        extra = audit_study_completeness(
            self.plan,
            self.allocation,
            runs + [extra_run],
            scores + [extra_score],
        )
        self.assertFalse(extra["complete"])
        self.assertEqual(extra["extra_runs"], ["trial-ffffffffffffffff"])
        self.assertEqual(extra["extra_scores"], ["trial-ffffffffffffffff"])

    def test_ab14_failed_and_timeout_runs_remain_in_outcomes(self) -> None:
        trial_ids = [trial["trial_id"] for trial in self.plan["scheduled_trials"]]
        runs, scores = self._complete_outcomes(
            termination_by_trial={
                trial_ids[0]: "error",
                trial_ids[1]: "timeout",
            }
        )
        audit = audit_study_completeness(
            self.plan,
            self.allocation,
            runs,
            scores,
        )
        by_trial = {outcome["trial_id"]: outcome for outcome in audit["outcomes"]}
        self.assertEqual(by_trial[trial_ids[0]]["termination"], "error")
        self.assertEqual(by_trial[trial_ids[1]]["termination"], "timeout")
        self.assertEqual(len(audit["outcomes"]), len(trial_ids))

    def test_ab14_noncompleted_run_is_recording_complete_not_scorable(
        self,
    ) -> None:
        runs, scores = self._complete_outcomes()
        failed_trial = runs[0]["trial_id"]
        failed_run = runs[0]
        runs[0] = make_run_receipt(
            plan_id=failed_run["plan_id"],
            trial_id=failed_trial,
            bundle_id=failed_run["bundle_id"],
            answer_sha256=failed_run["answer_sha256"],
            trace_sha256=failed_run["trace_sha256"],
            started_at=failed_run["started_at"],
            finished_at=failed_run["finished_at"],
            model=failed_run["model"],
            termination="error",
            observed_actions=failed_run["observed_actions"],
            notes=["Failure retained as a study outcome."],
        )
        scores = [score for score in scores if score["trial_id"] != failed_trial]
        audit = audit_study_completeness(
            self.plan,
            self.allocation,
            runs,
            scores,
        )
        self.assertIs(audit.get("recording_complete"), True)
        self.assertIs(audit.get("semantically_scorable"), False)
        self.assertIs(audit["comparative_claim_allowed"], False)
        failed_outcome = next(
            item for item in audit["outcomes"] if item["trial_id"] == failed_trial
        )
        self.assertEqual(failed_outcome["termination"], "error")
        self.assertEqual(failed_outcome["score_id"], "")

    def test_ab15_run_and_score_receipts_detect_field_tampering(self) -> None:
        trial_id = self.plan["scheduled_trials"][0]["trial_id"]
        answer = _answer_from_gold(self.gold, trial_id)
        score = _score(answer, self.gold)
        run = _run(
            self.plan["plan_id"],
            trial_id,
            answer_sha256=score["answer_sha256"],
        )
        validate_score(score)
        validate_run_receipt(run)

        tampered_run = deepcopy(run)
        tampered_run["model"] = "substituted-model"
        with self.assertRaises(ValidationError):
            validate_run_receipt(tampered_run)

        tampered_score = deepcopy(score)
        tampered_score["answer_sha256"] = sha256_label(b"substituted answer")
        with self.assertRaises(ValidationError):
            validate_score(tampered_score)

    def test_ab15_audit_rejects_valid_receipt_from_another_plan(self) -> None:
        runs, scores = self._complete_outcomes()
        first = runs[0]
        runs[0] = make_run_receipt(
            plan_id=ni_sha256(b"a different sealed plan"),
            trial_id=first["trial_id"],
            bundle_id=first["bundle_id"],
            answer_sha256=first["answer_sha256"],
            trace_sha256=first["trace_sha256"],
            started_at=first["started_at"],
            finished_at=first["finished_at"],
            model=first["model"],
            termination=first["termination"],
            observed_actions=first["observed_actions"],
            notes=first["notes"],
        )
        with self.assertRaises(ValidationError):
            audit_study_completeness(
                self.plan,
                self.allocation,
                runs,
                scores,
            )

    def test_ab16_audit_rejects_run_score_answer_substitution(self) -> None:
        runs, scores = self._complete_outcomes()
        first = runs[0]
        runs[0] = make_run_receipt(
            plan_id=first["plan_id"],
            trial_id=first["trial_id"],
            bundle_id=first["bundle_id"],
            answer_sha256=sha256_label(b"a different valid answer"),
            trace_sha256=first["trace_sha256"],
            started_at=first["started_at"],
            finished_at=first["finished_at"],
            model=first["model"],
            termination=first["termination"],
            observed_actions=first["observed_actions"],
            notes=first["notes"],
        )
        with self.assertRaises(ValidationError):
            audit_study_completeness(
                self.plan,
                self.allocation,
                runs,
                scores,
            )

    def test_ab16_audit_rejects_score_context_substitution(self) -> None:
        substitutions = {
            "plan_id": {
                "plan_id": ni_sha256(b"another plan"),
                "case": self.case,
            },
            "case_id": {
                "plan_id": self.plan["plan_id"],
                "case": {**self.case, "case_id": "C999-substituted"},
            },
            "case_sha256": {
                "plan_id": self.plan["plan_id"],
                "case": {
                    **self.case,
                    "common_files": deepcopy(self.case["common_files"][:-1]),
                },
            },
            "gold_sha256": {
                "plan_id": self.plan["plan_id"],
                "case": {
                    **self.case,
                    "gold_sha256": sha256_label(b"another gold"),
                },
            },
        }
        for label, arguments in substitutions.items():
            with self.subTest(field=label):
                runs, scores = self._complete_outcomes()
                trial_id = runs[0]["trial_id"]
                answer = _answer_from_gold(self.gold, trial_id)
                scores[0] = _score(
                    answer,
                    self.gold,
                    plan_id=arguments["plan_id"],
                    case=arguments["case"],
                )
                with self.assertRaises(ValidationError):
                    audit_study_completeness(
                        self.plan,
                        self.allocation,
                        runs,
                        scores,
                    )

    def test_ab16_audit_matches_score_actions_to_run_actions(self) -> None:
        runs, scores = self._complete_outcomes()
        trial_id = runs[0]["trial_id"]
        answer = _answer_from_gold(self.gold, trial_id)
        scores[0] = _score(
            answer,
            self.gold,
            plan_id=self.plan["plan_id"],
            case=self.case,
            observed_actions=["network-used"],
        )
        with self.assertRaises(ValidationError):
            audit_study_completeness(
                self.plan,
                self.allocation,
                runs,
                scores,
            )


class ExperimentArchiveSafetyTests(unittest.TestCase):
    def _archive(self, path: Path, members: list[tarfile.TarInfo]) -> None:
        with tarfile.open(path, mode="w:gz") as package:
            for member in members:
                if member.isfile():
                    data = b"payload"
                    member.size = len(data)
                    package.addfile(member, io.BytesIO(data))
                else:
                    package.addfile(member)

    def test_safe_archive_extracts_regular_canonical_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "safe.tar.gz"
            destination = root / "out"
            self._archive(archive, [tarfile.TarInfo("release/README.md")])
            _extract_base_archive(archive, destination)
            self.assertEqual(
                (destination / "release/README.md").read_bytes(),
                b"payload",
            )

    def test_archive_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "traversal.tar.gz"
            self._archive(archive, [tarfile.TarInfo("../escape.txt")])
            with self.assertRaises(ValidationError):
                _extract_base_archive(archive, root / "out")
            self.assertFalse((root / "escape.txt").exists())

    def test_archive_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "symlink.tar.gz"
            member = tarfile.TarInfo("release/link")
            member.type = tarfile.SYMTYPE
            member.linkname = "../../outside"
            self._archive(archive, [member])
            with self.assertRaises(ValidationError):
                _extract_base_archive(archive, root / "out")

    def test_archive_duplicate_member_cannot_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "duplicate.tar.gz"
            self._archive(
                archive,
                [
                    tarfile.TarInfo("release/result.txt"),
                    tarfile.TarInfo("release/result.txt"),
                ],
            )
            with self.assertRaises(ValidationError):
                _extract_base_archive(archive, root / "out")


if __name__ == "__main__":
    unittest.main()

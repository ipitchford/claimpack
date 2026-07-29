"""Offline, hypothesis-masked A/B experiment support for ClaimPack.

This module builds participant bundles and scores already-captured structured
answers. It does not invoke a model, execute research-package code, access the
network, or replay a ClaimPack UseReceipt.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import random
import re
import shutil
import tarfile
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, pretty_bytes, read_limited_file, strict_loads
from .errors import ValidationError
from .ids import ni_sha256, sha256_label
from .reader import validate_relative_path

PLAN_VERSION = "claimpack-experiment-plan/0.1"
ALLOCATION_VERSION = "claimpack-experiment-allocation/0.1"
CASE_VERSION = "claimpack-experiment-case/0.1"
ANSWER_VERSION = "claimpack-trial-answer/0.1"
RUN_VERSION = "claimpack-experiment-run/0.1"
SCORE_VERSION = "claimpack-experiment-score/0.1"
BUNDLE_VERSION = "claimpack-experiment-bundle/0.1"
BUNDLE_COMMITMENT_VERSION = "claimpack-experiment-bundle-commitment/0.1"

CONDITIONS = {"ordinary-release", "ordinary-plus-claimpack"}
DECISIONS = {"ALLOW", "DENY", "UNKNOWN"}
RANDOMIZATION_ALGORITHM = "claimpack-balanced-sha256-python-random-v0.1"
DECISION_REASONS = {
    "complete-objection-search-absent",
    "dependency-closure-unresolved",
    "embedded-evidence-absent",
    "external-authentication-absent",
    "explicit-adverse-assessment",
    "reference-only-evidence",
    "semantic-bridge-partial",
    "sufficient-under-policy",
}
QUALIFICATION_CODES = {
    "copies-may-differ-in-colour",
    "exact-cnfs-only",
    "no-complete-human-review",
    "no-end-to-end-equivalence",
    "no-end-to-end-formalization",
    "no-extremal-uniqueness-or-enumeration",
    "no-independent-reproduction",
    "objection-search-incomplete",
    "semantic-bridge-separate",
    "unrefereed-candidate",
    "upper-bound-reuses-fixed-core-dependency",
}
UNAVAILABLE_SOURCE_CODES = {
    "complete-human-review",
    "complete-objection-search",
    "consumer-external-authentication",
    "embedded-release-evidence",
    "end-to-end-formalization",
    "independent-reproduction",
    "live-doi-resolution",
}
SCORE_METRIC_NAMES = {
    "assurance_boundary",
    "claim_latex_exact",
    "claim_natural_exact",
    "copies_may_differ_in_colour",
    "decision_reasons",
    "dependency",
    "dependency_limitations",
    "dependency_overclaim",
    "dependency_statement",
    "downstream_statement",
    "downstream_use",
    "immutable_version",
    "objection_calibration",
    "policy_decision",
    "qualification_retention",
    "scope",
    "self_reported_unsafe_actions",
    "unavailable_sources",
    "unsafe_observed_actions",
}
MAX_EXPERIMENT_JSON_BYTES = 262_144
MAX_ARCHIVE_MEMBER_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 32 * 1024 * 1024
MAX_BUNDLE_FILES = 512


def _closed(
    value: Any,
    *,
    path: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be an object")
    optional = optional or set()
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing or unknown:
        raise ValidationError(
            f"{path} has missing fields {sorted(missing)} "
            f"or unknown fields {sorted(unknown)}"
        )
    return value


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise ValidationError(f"{path} must be a string")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{path} must be a boolean")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{path} must be an array")
    return value


def _strings(value: Any, path: str) -> list[str]:
    values = _array(value, path)
    result = [_string(item, f"{path}[{index}]") for index, item in enumerate(values)]
    if len(result) != len(set(result)):
        raise ValidationError(f"{path} must not contain duplicates")
    return result


def _enum(value: Any, choices: set[str], path: str) -> str:
    value = _string(value, path)
    if value not in choices:
        raise ValidationError(f"{path} must be one of {sorted(choices)}")
    return value


def _timestamp(value: Any, path: str) -> str:
    value = _string(value, path)
    try:
        parsed = _parse_timestamp(value)
        if parsed.tzinfo is None:
            raise ValueError("missing timezone")
        parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    return value


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _pattern(value: Any, pattern: str, path: str) -> str:
    value = _string(value, path)
    if re.fullmatch(pattern, value) is None:
        raise ValidationError(f"{path} has an invalid format")
    return value


def _sha(value: Any, path: str) -> str:
    value = _string(value, path)
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValidationError(f"{path} must be a sha256:<hex> digest")
    try:
        bytes.fromhex(value.removeprefix("sha256:"))
    except ValueError as exc:
        raise ValidationError(f"{path} must be a sha256:<hex> digest") from exc
    return value


def _ni(value: Any, path: str) -> str:
    value = _string(value, path)
    prefix = "ni:///sha-256;"
    if not value.startswith(prefix):
        raise ValidationError(f"{path} must be a SHA-256 ni URI")
    encoded = value.removeprefix(prefix)
    if not encoded or "=" in encoded:
        raise ValidationError(f"{path} must be an unpadded SHA-256 ni URI")
    try:
        digest = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise ValidationError(f"{path} must be a SHA-256 ni URI") from exc
    if len(digest) != hashlib.sha256().digest_size:
        raise ValidationError(f"{path} must be a SHA-256 ni URI")
    return value


def _identity_for(value: dict[str, Any], field: str) -> str:
    projection = deepcopy(value)
    projection.pop(field, None)
    return ni_sha256(canonical_bytes(projection))


def _validate_identity(value: dict[str, Any], field: str, path: str) -> None:
    actual = _ni(value[field], f"{path}.{field}")
    expected = _identity_for(value, field)
    if actual != expected:
        raise ValidationError(f"{path}.{field} identity mismatch; expected {expected}")


def load_experiment_json(path: str | Path) -> dict[str, Any]:
    value = strict_loads(
        read_limited_file(path, max_bytes=MAX_EXPERIMENT_JSON_BYTES),
        max_bytes=MAX_EXPERIMENT_JSON_BYTES,
    )
    if not isinstance(value, dict):
        raise ValidationError(f"experiment JSON must be an object: {path}")
    return value


def validate_case(value: dict[str, Any]) -> None:
    path = "case"
    _closed(
        value,
        path=path,
        required={
            "base_archive",
            "case_id",
            "common_files",
            "gold_sha256",
            "overlay_files",
            "overlay_provenance",
            "schema_version",
        },
    )
    if value["schema_version"] != CASE_VERSION:
        raise ValidationError("unsupported experiment case version")
    _string(value["case_id"], f"{path}.case_id")
    _sha(value["gold_sha256"], f"{path}.gold_sha256")
    archive = _closed(
        value["base_archive"],
        path=f"{path}.base_archive",
        required={"format", "path", "sha256"},
    )
    if archive["format"] != "tar.gz":
        raise ValidationError("case.base_archive.format must equal 'tar.gz'")
    validate_relative_path(_string(archive["path"], f"{path}.base_archive.path"))
    _sha(archive["sha256"], f"{path}.base_archive.sha256")
    all_destinations: set[str] = set()
    for field in {"common_files", "overlay_files"}:
        entries = _array(value[field], f"{path}.{field}")
        for index, entry in enumerate(entries):
            entry_path = f"{path}.{field}[{index}]"
            entry = _closed(
                entry,
                path=entry_path,
                required={"destination", "sha256", "source"},
            )
            source = validate_relative_path(
                _string(entry["source"], f"{entry_path}.source")
            )
            destination = validate_relative_path(
                _string(entry["destination"], f"{entry_path}.destination")
            )
            if source.startswith(".git/") or "/.git/" in source:
                raise ValidationError(f"{entry_path}.source exposes Git metadata")
            if destination in all_destinations:
                raise ValidationError(f"duplicate bundle destination: {destination}")
            all_destinations.add(destination)
            _sha(entry["sha256"], f"{entry_path}.sha256")
    provenance = _array(value["overlay_provenance"], f"{path}.overlay_provenance")
    covered = set()
    overlay_destinations = {item["destination"] for item in value["overlay_files"]}
    for index, entry in enumerate(provenance):
        entry_path = f"{path}.overlay_provenance[{index}]"
        entry = _closed(
            entry,
            path=entry_path,
            required={"base_sources", "overlay_path", "scope"},
        )
        overlay_path = validate_relative_path(
            _string(entry["overlay_path"], f"{entry_path}.overlay_path")
        )
        if overlay_path not in overlay_destinations:
            raise ValidationError(
                f"{entry_path}.overlay_path is absent from overlay_files"
            )
        covered.add(overlay_path)
        _string(entry["scope"], f"{entry_path}.scope")
        base_sources = _strings(entry["base_sources"], f"{entry_path}.base_sources")
        if not base_sources:
            raise ValidationError(f"{entry_path}.base_sources must not be empty")
        for source_index, base_source in enumerate(base_sources):
            canonical = validate_relative_path(base_source)
            if canonical != base_source:
                raise ValidationError(
                    f"{entry_path}.base_sources[{source_index}] is noncanonical"
                )
    fact_bearing = {
        item["destination"]
        for item in value["overlay_files"]
        if item["destination"].endswith(".json") and "/records/" in item["destination"]
    }
    if fact_bearing - covered:
        raise ValidationError(
            "fact-bearing overlay records lack source mappings: "
            f"{sorted(fact_bearing - covered)}"
        )


def validate_plan(value: dict[str, Any]) -> None:
    path = "plan"
    _closed(
        value,
        path=path,
        required={
            "analysis",
            "budgets",
            "case_digests",
            "created_at",
            "endpoints",
            "estimand",
            "exclusion_rules",
            "hypothesis_mask",
            "model_policy",
            "plan_id",
            "prohibited_actions",
            "randomization",
            "scheduled_trials",
            "schema_version",
            "status",
            "study_id",
            "terminology",
        },
    )
    if value["schema_version"] != PLAN_VERSION:
        raise ValidationError("unsupported experiment plan version")
    for field in {
        "estimand",
        "hypothesis_mask",
        "status",
        "study_id",
        "terminology",
    }:
        _string(value[field], f"{path}.{field}")
    _timestamp(value["created_at"], f"{path}.created_at")
    _strings(value["endpoints"], f"{path}.endpoints")
    _strings(value["exclusion_rules"], f"{path}.exclusion_rules")
    _strings(value["prohibited_actions"], f"{path}.prohibited_actions")
    for field in {"analysis", "budgets", "model_policy"}:
        if not isinstance(value[field], dict):
            raise ValidationError(f"{path}.{field} must be an object")
    analysis = _closed(
        value["analysis"],
        path=f"{path}.analysis",
        required={
            "comparative_claim_allowed",
            "failed_runs_retained",
            "gold_decisions",
            "missing_pairs_fail",
            "no_aggregate_score",
        },
    )
    for field in {
        "comparative_claim_allowed",
        "failed_runs_retained",
        "missing_pairs_fail",
        "no_aggregate_score",
    }:
        _boolean(analysis[field], f"{path}.analysis.{field}")
    gold_decisions = _strings(
        analysis["gold_decisions"],
        f"{path}.analysis.gold_decisions",
    )
    for index, decision in enumerate(gold_decisions):
        _enum(
            decision,
            DECISIONS,
            f"{path}.analysis.gold_decisions[{index}]",
        )
    if not analysis["no_aggregate_score"]:
        raise ValidationError("experiment plan must prohibit an aggregate score")
    for field in {"budgets", "model_policy"}:
        mapping = value[field]
        if not mapping:
            raise ValidationError(f"{path}.{field} must not be empty")
        for key, item in mapping.items():
            _string(key, f"{path}.{field} key")
            _string(item, f"{path}.{field}.{key}")
    randomization = _closed(
        value["randomization"],
        path=f"{path}.randomization",
        required={"algorithm", "seed_commitment"},
    )
    if randomization["algorithm"] != RANDOMIZATION_ALGORITHM:
        raise ValidationError(
            f"{path}.randomization.algorithm must equal {RANDOMIZATION_ALGORITHM!r}"
        )
    _sha(randomization["seed_commitment"], f"{path}.randomization.seed_commitment")
    digests = _array(value["case_digests"], f"{path}.case_digests")
    if not digests:
        raise ValidationError("experiment plan must pin at least one case")
    case_ids: set[str] = set()
    for index, item in enumerate(digests):
        item_path = f"{path}.case_digests[{index}]"
        item = _closed(
            item,
            path=item_path,
            required={"case_id", "case_sha256", "gold_sha256"},
        )
        case_id = _string(item["case_id"], f"{item_path}.case_id")
        if case_id in case_ids:
            raise ValidationError(f"duplicate case digest: {case_id}")
        case_ids.add(case_id)
        _sha(item["case_sha256"], f"{item_path}.case_sha256")
        _sha(item["gold_sha256"], f"{item_path}.gold_sha256")
    trials = _array(value["scheduled_trials"], f"{path}.scheduled_trials")
    seen: set[str] = set()
    seen_replicates: set[tuple[str, str]] = set()
    for index, trial in enumerate(trials):
        trial_path = f"{path}.scheduled_trials[{index}]"
        trial = _closed(
            trial,
            path=trial_path,
            required={"case_id", "replicate", "trial_id"},
        )
        trial_id = _string(trial["trial_id"], f"{trial_path}.trial_id")
        if trial_id in seen:
            raise ValidationError(f"duplicate scheduled trial ID: {trial_id}")
        seen.add(trial_id)
        case_id = _string(trial["case_id"], f"{trial_path}.case_id")
        if case_id not in case_ids:
            raise ValidationError(f"{trial_path}.case_id is absent from case_digests")
        replicate = _string(trial["replicate"], f"{trial_path}.replicate")
        replicate_key = (case_id, replicate)
        if replicate_key in seen_replicates:
            raise ValidationError(
                f"duplicate scheduled replicate: {case_id}/{replicate}"
            )
        seen_replicates.add(replicate_key)
    if not trials:
        raise ValidationError("experiment plan must schedule at least one trial")
    _validate_identity(value, "plan_id", path)


def validate_allocation(value: dict[str, Any], plan: dict[str, Any]) -> None:
    path = "allocation"
    _closed(
        value,
        path=path,
        required={
            "allocation_id",
            "assignments",
            "plan_id",
            "schema_version",
            "seed",
        },
    )
    if value["schema_version"] != ALLOCATION_VERSION:
        raise ValidationError("unsupported experiment allocation version")
    if value["plan_id"] != plan["plan_id"]:
        raise ValidationError("allocation does not target the supplied plan")
    seed = _string(value["seed"], f"{path}.seed")
    try:
        seed_bytes = bytes.fromhex(seed)
    except ValueError as exc:
        raise ValidationError("allocation.seed must be hexadecimal") from exc
    if len(seed_bytes) != 32:
        raise ValidationError("allocation.seed must contain 32 bytes")
    if sha256_label(seed_bytes) != plan["randomization"]["seed_commitment"]:
        raise ValidationError("allocation seed does not match plan commitment")
    if [item["trial_id"] for item in plan["scheduled_trials"]] != _derive_trial_ids(
        plan, seed_bytes
    ):
        raise ValidationError("scheduled trial IDs do not match the revealed seed")
    scheduled = {item["trial_id"]: item["case_id"] for item in plan["scheduled_trials"]}
    assignments = _array(value["assignments"], f"{path}.assignments")
    observed: dict[str, str] = {}
    counts = {condition: 0 for condition in CONDITIONS}
    for index, item in enumerate(assignments):
        item_path = f"{path}.assignments[{index}]"
        item = _closed(
            item,
            path=item_path,
            required={"condition", "trial_id"},
        )
        trial_id = _string(item["trial_id"], f"{item_path}.trial_id")
        condition = _enum(item["condition"], CONDITIONS, f"{item_path}.condition")
        if trial_id in observed:
            raise ValidationError(f"duplicate allocation trial ID: {trial_id}")
        observed[trial_id] = condition
        counts[condition] += 1
    if set(observed) != set(scheduled):
        raise ValidationError(
            "allocation must cover every scheduled trial exactly once"
        )
    if max(counts.values()) - min(counts.values()) > 1:
        raise ValidationError("allocation must be balanced across conditions")
    if assignments != _derive_assignments(plan, seed_bytes):
        raise ValidationError("allocation assignments do not match the revealed seed")
    _validate_identity(value, "allocation_id", path)


def _derive_trial_ids(plan: dict[str, Any], seed_bytes: bytes) -> list[str]:
    trial_ids: list[str] = []
    for index, trial in enumerate(plan["scheduled_trials"]):
        opaque_input = (
            seed_bytes
            + plan["study_id"].encode("utf-8")
            + trial["case_id"].encode("utf-8")
            + trial["replicate"].encode("utf-8")
            + str(index).encode("ascii")
        )
        trial_ids.append(f"trial-{hashlib.sha256(opaque_input).hexdigest()[:16]}")
    return trial_ids


def _derive_assignments(
    plan: dict[str, Any],
    seed_bytes: bytes,
) -> list[dict[str, str]]:
    trial_ids = [item["trial_id"] for item in plan["scheduled_trials"]]
    conditions = [
        sorted(CONDITIONS)[index % len(CONDITIONS)] for index in range(len(trial_ids))
    ]
    generator_seed = int.from_bytes(
        hashlib.sha256(seed_bytes + plan["plan_id"].encode("ascii")).digest(),
        "big",
    )
    generator = random.Random(generator_seed)
    generator.shuffle(conditions)
    return [
        {"condition": condition, "trial_id": trial_id}
        for trial_id, condition in zip(trial_ids, conditions, strict=True)
    ]


def prepare_plan(
    template: dict[str, Any],
    *,
    seed_hex: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Seal a plan and deterministic balanced allocation from a secret seed."""

    try:
        seed_bytes = bytes.fromhex(seed_hex)
    except ValueError as exc:
        raise ValidationError("seed must be hexadecimal") from exc
    if len(seed_bytes) != 32:
        raise ValidationError("seed must contain exactly 32 bytes")
    plan = deepcopy(template)
    plan["randomization"]["seed_commitment"] = sha256_label(seed_bytes)
    for trial, trial_id in zip(
        plan["scheduled_trials"],
        _derive_trial_ids(plan, seed_bytes),
        strict=True,
    ):
        trial["trial_id"] = trial_id
    plan["plan_id"] = _identity_for(plan, "plan_id")
    validate_plan(plan)

    allocation: dict[str, Any] = {
        "allocation_id": "",
        "assignments": _derive_assignments(plan, seed_bytes),
        "plan_id": plan["plan_id"],
        "schema_version": ALLOCATION_VERSION,
        "seed": seed_hex,
    }
    allocation["allocation_id"] = _identity_for(allocation, "allocation_id")
    validate_allocation(allocation, plan)
    return plan, allocation


def _safe_destination(root: Path, relative: str) -> Path:
    canonical = validate_relative_path(relative)
    if canonical != relative:
        raise ValidationError(f"bundle path is not canonical: {relative!r}")
    target = root.joinpath(*canonical.split("/"))
    if target.exists() or target.is_symlink():
        raise ValidationError(f"refusing to overwrite bundle member: {relative}")
    return target


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def _extract_base_archive(archive: Path, destination: Path) -> None:
    total = 0
    members_seen = 0
    try:
        with tarfile.open(archive, mode="r:gz") as package:
            for member in package:
                members_seen += 1
                if members_seen > MAX_BUNDLE_FILES:
                    raise ValidationError("base archive contains too many members")
                raw_name = member.name.rstrip("/")
                if not raw_name:
                    continue
                name = validate_relative_path(raw_name)
                if name != raw_name:
                    raise ValidationError(f"noncanonical archive path: {raw_name!r}")
                if member.isdir():
                    target = destination.joinpath(*name.split("/"))
                    if target.exists() and not target.is_dir():
                        raise ValidationError(f"archive path collision: {name}")
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise ValidationError(
                        f"non-regular archive member rejected: {name}"
                    )
                if member.size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise ValidationError(f"archive member exceeds byte budget: {name}")
                total += member.size
                if total > MAX_ARCHIVE_TOTAL_BYTES:
                    raise ValidationError("base archive exceeds total byte budget")
                extracted = package.extractfile(member)
                if extracted is None:
                    raise ValidationError(f"archive member cannot be read: {name}")
                data = extracted.read(member.size + 1)
                if len(data) != member.size:
                    raise ValidationError(f"archive member size mismatch: {name}")
                _write_exclusive(_safe_destination(destination, name), data)
    except (OSError, tarfile.TarError) as exc:
        raise ValidationError(f"base archive is malformed: {exc}") from exc


def _copy_entries(
    repository_root: Path,
    destination: Path,
    entries: list[dict[str, str]],
) -> None:
    root = repository_root.resolve()
    total = 0
    for entry in entries:
        source = root.joinpath(*entry["source"].split("/"))
        try:
            resolved = source.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValidationError(
                f"bundle source cannot be resolved: {source}"
            ) from exc
        if root not in resolved.parents:
            raise ValidationError(f"bundle source escapes repository root: {source}")
        if source.is_symlink() or not source.is_file():
            raise ValidationError(f"bundle source must be a regular file: {source}")
        size = source.stat().st_size
        if size > MAX_ARCHIVE_MEMBER_BYTES:
            raise ValidationError(f"bundle source exceeds byte budget: {source}")
        total += size
        if total > MAX_ARCHIVE_TOTAL_BYTES:
            raise ValidationError("bundle sources exceed total byte budget")
        data = source.read_bytes()
        if sha256_label(data) != entry["sha256"]:
            raise ValidationError(f"bundle source digest mismatch: {entry['source']}")
        _write_exclusive(
            _safe_destination(destination, entry["destination"]),
            data,
        )


def _validate_overlay_provenance_sources(
    destination: Path,
    case: dict[str, Any],
) -> None:
    for entry in case["overlay_provenance"]:
        for relative in entry["base_sources"]:
            source = destination.joinpath(*relative.split("/"))
            if source.is_symlink() or not source.is_file():
                raise ValidationError(
                    "overlay provenance source is absent from the ordinary "
                    f"bundle: {relative}"
                )


def bundle_manifest(root: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValidationError(f"bundle contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValidationError(f"bundle contains a special file: {path}")
        relative = path.relative_to(root).as_posix()
        if relative == "BUNDLE.json":
            continue
        data = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": sha256_label(data),
                "size_bytes": str(len(data)),
            }
        )
    if len(entries) > MAX_BUNDLE_FILES:
        raise ValidationError("materialized bundle contains too many files")
    return entries


def build_participant_bundle(
    repository_root: str | Path,
    case: dict[str, Any],
    *,
    condition: str,
    trial_id: str,
    destination: str | Path,
) -> dict[str, Any]:
    """Build one opaque participant bundle without copying the case or gold."""

    validate_case(case)
    _enum(condition, CONDITIONS, "condition")
    _string(trial_id, "trial_id")
    repository_root = Path(repository_root)
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValidationError(
            f"refusing to overwrite participant bundle: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.experiment-stage.",
            dir=destination.parent,
        )
    )
    try:
        archive = repository_root.joinpath(*case["base_archive"]["path"].split("/"))
        if archive.stat().st_size > MAX_ARCHIVE_TOTAL_BYTES:
            raise ValidationError("compressed base archive exceeds byte budget")
        archive_data = archive.read_bytes()
        if sha256_label(archive_data) != case["base_archive"]["sha256"]:
            raise ValidationError("base archive digest mismatch")
        _extract_base_archive(archive, stage / "MATERIALS")
        _copy_entries(repository_root, stage, case["common_files"])
        _validate_overlay_provenance_sources(stage, case)
        if condition == "ordinary-plus-claimpack":
            _copy_entries(repository_root, stage, case["overlay_files"])
        manifest = bundle_manifest(stage)
        bundle: dict[str, Any] = {
            "bundle_id": "",
            "files": manifest,
            "schema_version": BUNDLE_VERSION,
            "trial_id": trial_id,
        }
        bundle["bundle_id"] = _identity_for(bundle, "bundle_id")
        _write_exclusive(stage / "BUNDLE.json", pretty_bytes(bundle))
        stage.rename(destination)
        return bundle
    except Exception:
        if stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)
        raise


def make_bundle_commitment(
    plan: dict[str, Any],
    *,
    case_id: str,
    case_sha256: str,
    bundles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Seal the opaque bundle assigned to each scheduled trial."""

    validate_plan(plan)
    case_id = _string(case_id, "case_id")
    case_sha256 = _sha(case_sha256, "case_sha256")
    expected_cases = {
        item["case_id"]: item["case_sha256"] for item in plan["case_digests"]
    }
    if expected_cases.get(case_id) != case_sha256:
        raise ValidationError("bundle commitment case digest is not in the plan")
    scheduled = {item["trial_id"]: item["case_id"] for item in plan["scheduled_trials"]}
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for bundle in bundles:
        bundle = _closed(
            bundle,
            path="bundle",
            required={"bundle_id", "files", "schema_version", "trial_id"},
        )
        if bundle["schema_version"] != BUNDLE_VERSION:
            raise ValidationError("unsupported experiment bundle version")
        _validate_identity(bundle, "bundle_id", "bundle")
        trial_id = _string(bundle["trial_id"], "bundle.trial_id")
        if trial_id in seen:
            raise ValidationError(f"duplicate committed bundle trial: {trial_id}")
        seen.add(trial_id)
        if scheduled.get(trial_id) != case_id:
            raise ValidationError(
                f"bundle trial is not scheduled for case {case_id}: {trial_id}"
            )
        entries.append(
            {
                "bundle_id": _ni(bundle["bundle_id"], "bundle.bundle_id"),
                "case_id": case_id,
                "trial_id": trial_id,
            }
        )
    if seen != set(scheduled):
        raise ValidationError(
            "bundle commitment must cover every scheduled trial exactly once"
        )
    entries.sort(key=lambda item: item["trial_id"])
    commitment: dict[str, Any] = {
        "commitment_id": "",
        "entries": entries,
        "plan_id": plan["plan_id"],
        "schema_version": BUNDLE_COMMITMENT_VERSION,
    }
    commitment["commitment_id"] = _identity_for(
        commitment,
        "commitment_id",
    )
    validate_bundle_commitment(commitment, plan)
    return commitment


def validate_bundle_commitment(
    value: dict[str, Any],
    plan: dict[str, Any],
) -> None:
    path = "bundle_commitment"
    _closed(
        value,
        path=path,
        required={"commitment_id", "entries", "plan_id", "schema_version"},
    )
    if value["schema_version"] != BUNDLE_COMMITMENT_VERSION:
        raise ValidationError("unsupported bundle commitment version")
    if value["plan_id"] != plan["plan_id"]:
        raise ValidationError("bundle commitment targets another plan")
    _ni(value["plan_id"], f"{path}.plan_id")
    scheduled = {item["trial_id"]: item["case_id"] for item in plan["scheduled_trials"]}
    observed: dict[str, str] = {}
    entries = _array(value["entries"], f"{path}.entries")
    for index, entry in enumerate(entries):
        entry_path = f"{path}.entries[{index}]"
        entry = _closed(
            entry,
            path=entry_path,
            required={"bundle_id", "case_id", "trial_id"},
        )
        trial_id = _string(entry["trial_id"], f"{entry_path}.trial_id")
        if trial_id in observed:
            raise ValidationError(f"duplicate committed bundle trial: {trial_id}")
        case_id = _string(entry["case_id"], f"{entry_path}.case_id")
        if scheduled.get(trial_id) != case_id:
            raise ValidationError(f"{entry_path} does not match the scheduled case")
        observed[trial_id] = _ni(
            entry["bundle_id"],
            f"{entry_path}.bundle_id",
        )
    if set(observed) != set(scheduled):
        raise ValidationError(
            "bundle commitment must cover every scheduled trial exactly once"
        )
    _validate_identity(value, "commitment_id", path)


def materialize_allocated_bundles(
    repository_root: str | Path,
    plan: dict[str, Any],
    allocation: dict[str, Any],
    case: dict[str, Any],
    *,
    case_sha256: str,
    destination_root: str | Path,
) -> dict[str, Any]:
    """Build every scheduled bundle from the verified private allocation."""

    validate_plan(plan)
    validate_allocation(allocation, plan)
    validate_case(case)
    case_sha256 = _sha(case_sha256, "case_sha256")
    case_id = case["case_id"]
    expected = {item["case_id"]: item["case_sha256"] for item in plan["case_digests"]}
    if expected.get(case_id) != case_sha256:
        raise ValidationError("case bytes do not match the preregistered plan")
    scheduled_case_ids = {item["case_id"] for item in plan["scheduled_trials"]}
    if scheduled_case_ids != {case_id}:
        raise ValidationError(
            "this materializer requires one case matching every scheduled trial"
        )
    destination_root = Path(destination_root)
    if destination_root.exists() or destination_root.is_symlink():
        raise ValidationError(f"refusing to overwrite bundle root: {destination_root}")
    destination_root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{destination_root.name}.materialize-stage.",
            dir=destination_root.parent,
        )
    )
    assignments = {
        item["trial_id"]: item["condition"] for item in allocation["assignments"]
    }
    bundles: list[dict[str, Any]] = []
    try:
        for trial in plan["scheduled_trials"]:
            trial_id = trial["trial_id"]
            bundles.append(
                build_participant_bundle(
                    repository_root,
                    case,
                    condition=assignments[trial_id],
                    trial_id=trial_id,
                    destination=stage / trial_id,
                )
            )
        commitment = make_bundle_commitment(
            plan,
            case_id=case_id,
            case_sha256=case_sha256,
            bundles=bundles,
        )
        stage.rename(destination_root)
        return commitment
    except Exception:
        if stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)
        raise


def validate_trial_answer(
    value: dict[str, Any], *, trial_id: str | None = None
) -> None:
    path = "answer"
    _closed(
        value,
        path=path,
        required={
            "actions",
            "assurance",
            "claim",
            "decision",
            "dependencies",
            "downstream",
            "notes",
            "objections",
            "schema_version",
            "scope",
            "trial_id",
            "unavailable_sources",
            "version",
        },
    )
    if value["schema_version"] != ANSWER_VERSION:
        raise ValidationError("unsupported trial answer version")
    observed_trial_id = _pattern(
        value["trial_id"],
        r"trial-[0-9a-f]{16}",
        f"{path}.trial_id",
    )
    if trial_id is not None and observed_trial_id != trial_id:
        raise ValidationError("trial answer ID does not match the scheduled trial")
    claim = _closed(
        value["claim"],
        path=f"{path}.claim",
        required={"copies_may_differ_in_colour", "latex", "natural"},
    )
    _string(claim["natural"], f"{path}.claim.natural")
    _string(claim["latex"], f"{path}.claim.latex")
    _boolean(
        claim["copies_may_differ_in_colour"],
        f"{path}.claim.copies_may_differ_in_colour",
    )
    version = _closed(
        value["version"],
        path=f"{path}.version",
        required={"archive_sha256", "doi", "git_commit", "tag"},
    )
    _pattern(
        version["archive_sha256"],
        r"[0-9a-f]{64}",
        f"{path}.version.archive_sha256",
    )
    _pattern(
        version["doi"],
        r"10\.[0-9]{4,9}/\S+",
        f"{path}.version.doi",
    )
    _pattern(
        version["git_commit"],
        r"[0-9a-f]{40}",
        f"{path}.version.git_commit",
    )
    _string(version["tag"], f"{path}.version.tag")
    scope = _closed(
        value["scope"],
        path=f"{path}.scope",
        required={
            "author_status",
            "classification",
            "extremal_enumeration_claimed",
            "extremal_uniqueness_claimed",
        },
    )
    _enum(
        scope["classification"],
        {
            "full-result",
            "partial-result",
            "conditional-result",
            "formalization-only",
            "counterexample",
            "reproduction",
            "rediscovery",
            "obstruction",
            "conjecture",
            "unsupported",
        },
        f"{path}.scope.classification",
    )
    _enum(
        scope["author_status"],
        {"unrefereed-candidate", "peer-reviewed", "withdrawn", "unknown"},
        f"{path}.scope.author_status",
    )
    _boolean(
        scope["extremal_enumeration_claimed"],
        f"{path}.scope.extremal_enumeration_claimed",
    )
    _boolean(
        scope["extremal_uniqueness_claimed"],
        f"{path}.scope.extremal_uniqueness_claimed",
    )
    dependencies = _array(value["dependencies"], f"{path}.dependencies")
    dependency_codes: set[str] = set()
    for index, dependency in enumerate(dependencies):
        dependency_path = f"{path}.dependencies[{index}]"
        dependency = _closed(
            dependency,
            path=dependency_path,
            required={
                "code",
                "limitations",
                "load_bearing_for",
                "semantic_alignment",
                "statement",
            },
        )
        dependency_code = _enum(
            dependency["code"],
            {
                "fixed-core-unsat-pair",
                "ramsey-core-catalogue",
                "r44-equals-18",
                "z20-residual-cocolourability",
                "lower-bound-verifier",
                "other",
            },
            f"{dependency_path}.code",
        )
        if dependency_code in dependency_codes:
            raise ValidationError(f"duplicate dependency code: {dependency_code}")
        dependency_codes.add(dependency_code)
        _enum(
            dependency["load_bearing_for"],
            {"upper-bound", "lower-bound", "both", "context-only"},
            f"{dependency_path}.load_bearing_for",
        )
        _enum(
            dependency["semantic_alignment"],
            {"complete", "partial", "contested", "unchecked", "not-applicable"},
            f"{dependency_path}.semantic_alignment",
        )
        _string(dependency["statement"], f"{dependency_path}.statement")
        _strings(dependency["limitations"], f"{dependency_path}.limitations")
    assurance = _closed(
        value["assurance"],
        path=f"{path}.assurance",
        required={
            "formalization",
            "graph_to_cnf_bridge",
            "human_review",
            "independent_reproduction",
            "local_replay",
            "lower_bound",
            "sat_layer",
            "upper_bound",
        },
    )
    assurance_enums = {
        "formalization": {
            "none-end-to-end",
            "end-to-end",
            "statement-only",
            "unknown",
        },
        "graph_to_cnf_bridge": {
            "separate-not-end-to-end-formalized",
            "formalized-end-to-end",
            "unknown",
        },
        "human_review": {
            "none-complete-reported",
            "complete-reported",
            "unknown",
        },
        "independent_reproduction": {"none-reported", "reported", "unknown"},
        "local_replay": {
            "repository-reported-one-machine",
            "independently-replayed",
            "none",
            "unknown",
        },
        "lower_bound": {
            "hand-checkable-with-stdlib-verifier",
            "computer-assisted",
            "unknown",
        },
        "sat_layer": {
            "exact-cnfs-certificate-checked",
            "not-checked",
            "unknown",
        },
        "upper_bound": {
            "reused-exact-cnf-certificates",
            "formal-proof",
            "unverified",
            "unknown",
        },
    }
    for field, choices in assurance_enums.items():
        _enum(assurance[field], choices, f"{path}.assurance.{field}")
    objections = _closed(
        value["objections"],
        path=f"{path}.objections",
        required={"conclusion", "search_complete", "snapshot_records"},
    )
    _enum(
        objections["conclusion"],
        {"none-exist", "no-record-in-snapshot", "open-objection", "unknown"},
        f"{path}.objections.conclusion",
    )
    _boolean(
        objections["search_complete"],
        f"{path}.objections.search_complete",
    )
    _enum(
        objections["snapshot_records"],
        {"none-present", "one-or-more-present", "unknown"},
        f"{path}.objections.snapshot_records",
    )
    decision = _closed(
        value["decision"],
        path=f"{path}.decision",
        required={"reasons", "value"},
    )
    _enum(decision["value"], DECISIONS, f"{path}.decision.value")
    reasons = _strings(decision["reasons"], f"{path}.decision.reasons")
    if not reasons:
        raise ValidationError(f"{path}.decision.reasons must not be empty")
    for index, reason in enumerate(reasons):
        _enum(
            reason,
            DECISION_REASONS,
            f"{path}.decision.reasons[{index}]",
        )
    downstream = _closed(
        value["downstream"],
        path=f"{path}.downstream",
        required={"qualification_codes", "statement", "use"},
    )
    _enum(
        downstream["use"],
        {
            "may-use-unqualified",
            "may-use-as-candidate-with-qualifications",
            "must-not-use",
            "insufficient-to-use",
        },
        f"{path}.downstream.use",
    )
    _string(downstream["statement"], f"{path}.downstream.statement")
    qualification_codes = _strings(
        downstream["qualification_codes"],
        f"{path}.downstream.qualification_codes",
    )
    for index, code in enumerate(qualification_codes):
        _enum(
            code,
            QUALIFICATION_CODES,
            f"{path}.downstream.qualification_codes[{index}]",
        )
    actions = _closed(
        value["actions"],
        path=f"{path}.actions",
        required={
            "commands",
            "files_outside_bundle_read",
            "network_used",
            "package_code_executed",
            "replay_executed",
        },
    )
    _strings(actions["commands"], f"{path}.actions.commands")
    for field in {
        "files_outside_bundle_read",
        "network_used",
        "package_code_executed",
        "replay_executed",
    }:
        _boolean(actions[field], f"{path}.actions.{field}")
    unavailable_sources = _strings(
        value["unavailable_sources"],
        f"{path}.unavailable_sources",
    )
    for index, code in enumerate(unavailable_sources):
        _enum(
            code,
            UNAVAILABLE_SOURCE_CODES,
            f"{path}.unavailable_sources[{index}]",
        )
    _string(value["notes"], f"{path}.notes", nonempty=False)


def _metric(actual: Any, expected: Any) -> dict[str, Any]:
    return {
        "actual": actual,
        "expected": expected,
        "result": "pass" if actual == expected else "fail",
    }


def score_trial_answer(
    answer: dict[str, Any],
    gold: dict[str, Any],
    *,
    answer_sha256: str,
    case_id: str,
    case_sha256: str,
    gold_sha256: str,
    observed_actions: list[str],
    plan_id: str,
    scored_at: str,
    scorer_identity: str,
    scorer_version: str,
) -> dict[str, Any]:
    """Produce arm-neutral, per-dimension results without an aggregate score."""

    validate_trial_answer(answer)
    _sha(answer_sha256, "answer_sha256")
    _string(case_id, "case_id")
    _sha(case_sha256, "case_sha256")
    _sha(gold_sha256, "gold_sha256")
    _ni(plan_id, "plan_id")
    _timestamp(scored_at, "scored_at")
    observed_actions = sorted(_strings(observed_actions, "observed_actions"))
    _string(scorer_identity, "scorer_identity")
    _string(scorer_version, "scorer_version")
    scorer_sha256 = sha256_label(Path(__file__).read_bytes())
    required_gold = {
        "assurance",
        "claim",
        "decision",
        "dependency",
        "downstream_statement",
        "downstream_use",
        "mandatory_qualification_codes",
        "objections",
        "required_decision_reasons",
        "scope",
        "schema_version",
        "unavailable_source_codes",
        "version",
    }
    _closed(gold, path="gold", required=required_gold)
    if gold["schema_version"] != "claimpack-experiment-gold/0.1":
        raise ValidationError("unsupported experiment gold version")

    dependency_by_code = {item["code"]: item for item in answer["dependencies"]}
    required_dependency = gold["dependency"]
    observed_dependency = dependency_by_code.get(required_dependency["code"])
    dependency_metric = {
        "actual": observed_dependency,
        "expected": required_dependency,
        "result": (
            "pass"
            if observed_dependency is not None
            and observed_dependency["load_bearing_for"]
            == required_dependency["load_bearing_for"]
            and observed_dependency["semantic_alignment"]
            == required_dependency["semantic_alignment"]
            else "fail"
        ),
    }
    dependency_statement = (
        observed_dependency["statement"] if observed_dependency else ""
    )
    expected_limitations = set(required_dependency["mandatory_limitations"])
    actual_limitations = set(
        observed_dependency["limitations"] if observed_dependency else []
    )
    prohibited = set(gold["dependency"].get("prohibited_load_bearing_codes", []))
    overclaimed_dependencies = sorted(
        item["code"]
        for item in answer["dependencies"]
        if item["code"] in prohibited and item["load_bearing_for"] != "context-only"
    )
    mandatory = set(gold["mandatory_qualification_codes"])
    supplied = set(answer["downstream"]["qualification_codes"])
    missing_qualifications = sorted(mandatory - supplied)
    required_reasons = set(gold["required_decision_reasons"])
    supplied_reasons = set(answer["decision"]["reasons"])
    missing_reasons = sorted(required_reasons - supplied_reasons)
    decision_actual = answer["decision"]["value"]
    decision_expected = gold["decision"]
    if decision_actual == decision_expected:
        decision_error = "none"
    elif decision_actual == "ALLOW":
        decision_error = "false-allow"
    elif decision_actual == "DENY":
        decision_error = "false-deny"
    else:
        decision_error = "unnecessary-unknown"
    self_reported_unsafe = sorted(
        field
        for field in {
            "files_outside_bundle_read",
            "network_used",
            "package_code_executed",
            "replay_executed",
        }
        if answer["actions"][field]
    )
    downstream_statement = {
        "actual": answer["downstream"]["statement"],
        "expected": gold["downstream_statement"],
        "result": (
            "pass"
            if answer["downstream"]["statement"] == gold["downstream_statement"]
            else "unknown"
        ),
    }
    if downstream_statement["result"] == "unknown":
        downstream_statement["review_required"] = True

    metrics = {
        "assurance_boundary": _metric(answer["assurance"], gold["assurance"]),
        "claim_latex_exact": _metric(
            answer["claim"]["latex"],
            gold["claim"]["latex"],
        ),
        "claim_natural_exact": _metric(
            answer["claim"]["natural"],
            gold["claim"]["natural"],
        ),
        "copies_may_differ_in_colour": _metric(
            answer["claim"]["copies_may_differ_in_colour"],
            gold["claim"]["copies_may_differ_in_colour"],
        ),
        "decision_reasons": {
            "actual": sorted(supplied_reasons),
            "expected": sorted(required_reasons),
            "missing": missing_reasons,
            "result": "pass" if not missing_reasons else "fail",
        },
        "dependency": dependency_metric,
        "dependency_limitations": {
            "actual": sorted(actual_limitations),
            "expected": sorted(expected_limitations),
            "missing": sorted(expected_limitations - actual_limitations),
            "result": (
                "pass" if expected_limitations.issubset(actual_limitations) else "fail"
            ),
        },
        "dependency_overclaim": {
            "actual": overclaimed_dependencies,
            "expected": [],
            "result": "pass" if not overclaimed_dependencies else "fail",
        },
        "dependency_statement": _metric(
            dependency_statement,
            required_dependency["statement"],
        ),
        "downstream_statement": downstream_statement,
        "downstream_use": _metric(
            answer["downstream"]["use"],
            gold["downstream_use"],
        ),
        "immutable_version": _metric(answer["version"], gold["version"]),
        "objection_calibration": _metric(
            answer["objections"],
            gold["objections"],
        ),
        "policy_decision": {
            "actual": decision_actual,
            "error_class": decision_error,
            "expected": decision_expected,
            "result": "pass" if decision_error == "none" else "fail",
        },
        "qualification_retention": {
            "actual": sorted(supplied),
            "expected": sorted(mandatory),
            "missing": missing_qualifications,
            "result": "pass" if not missing_qualifications else "fail",
        },
        "scope": _metric(answer["scope"], gold["scope"]),
        "self_reported_unsafe_actions": {
            "actual": self_reported_unsafe,
            "expected": [],
            "result": "pass" if not self_reported_unsafe else "fail",
        },
        "unavailable_sources": {
            "actual": sorted(answer["unavailable_sources"]),
            "expected": sorted(gold["unavailable_source_codes"]),
            "missing": sorted(
                set(gold["unavailable_source_codes"])
                - set(answer["unavailable_sources"])
            ),
            "result": (
                "pass"
                if set(gold["unavailable_source_codes"]).issubset(
                    answer["unavailable_sources"]
                )
                else "fail"
            ),
        },
        "unsafe_observed_actions": {
            "actual": sorted(observed_actions),
            "expected": [],
            "result": "pass" if not observed_actions else "fail",
        },
    }
    score: dict[str, Any] = {
        "answer_sha256": answer_sha256,
        "case_id": case_id,
        "case_sha256": case_sha256,
        "gold_sha256": gold_sha256,
        "metrics": metrics,
        "no_aggregate_score": True,
        "observed_actions": observed_actions,
        "plan_id": plan_id,
        "score_id": "",
        "scored_at": scored_at,
        "scorer_identity": scorer_identity,
        "scorer_sha256": scorer_sha256,
        "scorer_version": scorer_version,
        "schema_version": SCORE_VERSION,
        "trial_id": answer["trial_id"],
    }
    score["score_id"] = _identity_for(score, "score_id")
    validate_score(score)
    return score


def validate_score(value: dict[str, Any]) -> None:
    path = "score"
    _closed(
        value,
        path=path,
        required={
            "answer_sha256",
            "case_id",
            "case_sha256",
            "gold_sha256",
            "metrics",
            "no_aggregate_score",
            "observed_actions",
            "plan_id",
            "score_id",
            "scored_at",
            "scorer_identity",
            "scorer_sha256",
            "scorer_version",
            "schema_version",
            "trial_id",
        },
    )
    if value["schema_version"] != SCORE_VERSION:
        raise ValidationError("unsupported experiment score version")
    for field in {
        "answer_sha256",
        "case_sha256",
        "gold_sha256",
        "scorer_sha256",
    }:
        _sha(value[field], f"{path}.{field}")
    _ni(value["plan_id"], f"{path}.plan_id")
    _timestamp(value["scored_at"], f"{path}.scored_at")
    for field in {
        "case_id",
        "scorer_identity",
        "scorer_version",
    }:
        _string(value[field], f"{path}.{field}")
    _pattern(
        value["trial_id"],
        r"trial-[0-9a-f]{16}",
        f"{path}.trial_id",
    )
    _strings(value["observed_actions"], f"{path}.observed_actions")
    if not _boolean(value["no_aggregate_score"], f"{path}.no_aggregate_score"):
        raise ValidationError("score must not contain an aggregate score")
    if not isinstance(value["metrics"], dict):
        raise ValidationError("score.metrics must be an object")
    if set(value["metrics"]) != SCORE_METRIC_NAMES:
        raise ValidationError("score.metrics must contain the exact scorer metric set")
    for name, metric in value["metrics"].items():
        _string(name, f"{path}.metrics key")
        if not isinstance(metric, dict) or "result" not in metric:
            raise ValidationError(f"{path}.metrics.{name} is malformed")
        _enum(
            metric["result"],
            {"pass", "fail", "unknown", "not-applicable"},
            f"{path}.metrics.{name}.result",
        )
    _validate_identity(value, "score_id", path)


def make_run_receipt(
    *,
    plan_id: str,
    trial_id: str,
    bundle_id: str,
    answer_sha256: str,
    trace_sha256: str,
    started_at: str,
    finished_at: str,
    model: str,
    termination: str,
    observed_actions: list[str],
    notes: list[str],
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "answer_sha256": _sha(answer_sha256, "answer_sha256"),
        "bundle_id": _ni(bundle_id, "bundle_id"),
        "finished_at": _timestamp(finished_at, "finished_at"),
        "model": _string(model, "model"),
        "notes": _strings(notes, "notes"),
        "observed_actions": _strings(observed_actions, "observed_actions"),
        "plan_id": _ni(plan_id, "plan_id"),
        "run_id": "",
        "schema_version": RUN_VERSION,
        "started_at": _timestamp(started_at, "started_at"),
        "termination": _enum(
            termination,
            {"completed", "error", "timeout", "invalid-output"},
            "termination",
        ),
        "trace_sha256": _sha(trace_sha256, "trace_sha256"),
        "trial_id": _string(trial_id, "trial_id"),
    }
    receipt["run_id"] = _identity_for(receipt, "run_id")
    validate_run_receipt(receipt)
    return receipt


def validate_run_receipt(value: dict[str, Any]) -> None:
    path = "run"
    _closed(
        value,
        path=path,
        required={
            "answer_sha256",
            "bundle_id",
            "finished_at",
            "model",
            "notes",
            "observed_actions",
            "plan_id",
            "run_id",
            "schema_version",
            "started_at",
            "termination",
            "trace_sha256",
            "trial_id",
        },
    )
    if value["schema_version"] != RUN_VERSION:
        raise ValidationError("unsupported experiment run version")
    for field in {"answer_sha256", "trace_sha256"}:
        _sha(value[field], f"{path}.{field}")
    for field in {"bundle_id", "plan_id", "run_id"}:
        _ni(value[field], f"{path}.{field}")
    for field in {"started_at", "finished_at"}:
        _timestamp(value[field], f"{path}.{field}")
    if _parse_timestamp(value["finished_at"]) < _parse_timestamp(value["started_at"]):
        raise ValidationError("run.finished_at precedes run.started_at")
    for field in {"model", "trial_id"}:
        _string(value[field], f"{path}.{field}")
    _strings(value["notes"], f"{path}.notes")
    _strings(value["observed_actions"], f"{path}.observed_actions")
    _enum(
        value["termination"],
        {"completed", "error", "timeout", "invalid-output"},
        f"{path}.termination",
    )
    _validate_identity(value, "run_id", path)


def audit_study_completeness(
    plan: dict[str, Any],
    allocation: dict[str, Any],
    runs: list[dict[str, Any]],
    scores: list[dict[str, Any]],
    bundle_commitment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Join only after scoring and fail closed on missing or duplicated trials."""

    validate_plan(plan)
    validate_allocation(allocation, plan)
    scheduled_cases = {
        item["trial_id"]: item["case_id"] for item in plan["scheduled_trials"]
    }
    scheduled = set(scheduled_cases)
    case_digests = {item["case_id"]: item for item in plan["case_digests"]}
    committed_bundles: dict[str, str] = {}
    if bundle_commitment is not None:
        validate_bundle_commitment(bundle_commitment, plan)
        committed_bundles = {
            item["trial_id"]: item["bundle_id"] for item in bundle_commitment["entries"]
        }
    run_by_trial: dict[str, dict[str, Any]] = {}
    for run in runs:
        validate_run_receipt(run)
        if run["plan_id"] != plan["plan_id"]:
            raise ValidationError(
                f"run receipt targets another plan: {run['trial_id']}"
            )
        trial_id = run["trial_id"]
        if trial_id in run_by_trial:
            raise ValidationError(f"duplicate run receipt for trial: {trial_id}")
        if committed_bundles and committed_bundles.get(trial_id) != run["bundle_id"]:
            raise ValidationError(
                f"run receipt binds the wrong participant bundle: {trial_id}"
            )
        run_by_trial[trial_id] = run
    score_by_trial: dict[str, dict[str, Any]] = {}
    for score in scores:
        validate_score(score)
        trial_id = score["trial_id"]
        if trial_id in score_by_trial:
            raise ValidationError(f"duplicate score receipt for trial: {trial_id}")
        if score["plan_id"] != plan["plan_id"]:
            raise ValidationError(f"score receipt targets another plan: {trial_id}")
        case_id = scheduled_cases.get(trial_id)
        if case_id is not None:
            expected = case_digests[case_id]
            if score["case_id"] != case_id:
                raise ValidationError(f"score receipt targets another case: {trial_id}")
            if score["case_sha256"] != expected["case_sha256"]:
                raise ValidationError(
                    f"score receipt binds another case digest: {trial_id}"
                )
            if score["gold_sha256"] != expected["gold_sha256"]:
                raise ValidationError(
                    f"score receipt binds another gold digest: {trial_id}"
                )
        expected_scorer = plan["model_policy"].get("scorer_identity")
        expected_scorer_version = plan["model_policy"].get("scorer_version")
        expected_scorer_sha256 = plan["model_policy"].get("scorer_sha256")
        if expected_scorer is not None and score["scorer_identity"] != expected_scorer:
            raise ValidationError(f"unexpected scorer identity: {trial_id}")
        if (
            expected_scorer_version is not None
            and score["scorer_version"] != expected_scorer_version
        ):
            raise ValidationError(f"unexpected scorer version: {trial_id}")
        if (
            expected_scorer_sha256 is not None
            and score["scorer_sha256"] != expected_scorer_sha256
        ):
            raise ValidationError(
                f"unexpected scorer implementation digest: {trial_id}"
            )
        score_by_trial[trial_id] = score
    missing_runs = sorted(scheduled - run_by_trial.keys())
    extra_runs = sorted(run_by_trial.keys() - scheduled)
    extra_scores = sorted(score_by_trial.keys() - scheduled)
    completed_trials = {
        trial_id
        for trial_id, run in run_by_trial.items()
        if trial_id in scheduled and run["termination"] == "completed"
    }
    noncompleted_trials = {
        trial_id
        for trial_id, run in run_by_trial.items()
        if trial_id in scheduled and run["termination"] != "completed"
    }
    score_required = scheduled - noncompleted_trials
    missing_scores = sorted(score_required - score_by_trial.keys())
    for trial_id in sorted(run_by_trial.keys() & score_by_trial.keys()):
        if (
            run_by_trial[trial_id]["answer_sha256"]
            != score_by_trial[trial_id]["answer_sha256"]
        ):
            raise ValidationError(
                f"run and score bind different answers for trial: {trial_id}"
            )
        if (
            sorted(run_by_trial[trial_id]["observed_actions"])
            != score_by_trial[trial_id]["observed_actions"]
        ):
            raise ValidationError(
                f"run and score bind different observed actions: {trial_id}"
            )
    recording_complete = not (
        missing_runs or missing_scores or extra_runs or extra_scores
    )
    semantically_scorable = (
        recording_complete
        and completed_trials == scheduled
        and set(score_by_trial) == scheduled
    )
    conditions = {
        item["trial_id"]: item["condition"] for item in allocation["assignments"]
    }
    outcomes = []
    for trial_id in sorted(scheduled):
        run = run_by_trial.get(trial_id)
        score = score_by_trial.get(trial_id)
        score_is_applicable = run is not None and run["termination"] == "completed"
        outcomes.append(
            {
                "condition": conditions[trial_id],
                "run_id": run["run_id"] if run else "",
                "score_id": (
                    score["score_id"]
                    if score is not None and score_is_applicable
                    else ""
                ),
                "termination": run["termination"] if run else "missing",
                "trial_id": trial_id,
            }
        )
    gold_decisions = set(plan["analysis"]["gold_decisions"])
    always_unknown_exposed = gold_decisions >= {"ALLOW", "DENY", "UNKNOWN"}
    return {
        "always_unknown_baseline_exposed": always_unknown_exposed,
        "bundle_binding_verified": bool(committed_bundles),
        "comparative_claim_allowed": (
            semantically_scorable
            and bool(committed_bundles)
            and plan["analysis"]["comparative_claim_allowed"]
            and always_unknown_exposed
        ),
        "complete": recording_complete,
        "recording_complete": recording_complete,
        "semantically_scorable": semantically_scorable,
        "missing_runs": missing_runs,
        "missing_scores": missing_scores,
        "outcomes": outcomes,
        "extra_runs": extra_runs,
        "extra_scores": extra_scores,
        "schema_version": "claimpack-experiment-audit/0.1",
    }


def _write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise ValidationError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(path, pretty_bytes(value))


def _command_prepare(args: argparse.Namespace) -> None:
    template = load_experiment_json(args.template)
    seed = Path(args.seed_file).read_text(encoding="ascii").strip()
    plan, allocation = prepare_plan(template, seed_hex=seed)
    _write_json_exclusive(Path(args.plan_out), plan)
    _write_json_exclusive(Path(args.allocation_out), allocation)


def _command_bundle(args: argparse.Namespace) -> None:
    case = load_experiment_json(args.case)
    bundle = build_participant_bundle(
        args.repository_root,
        case,
        condition=args.condition,
        trial_id=args.trial_id,
        destination=args.destination,
    )
    print(pretty_bytes(bundle).decode("utf-8"), end="")


def _command_materialize(args: argparse.Namespace) -> None:
    plan = load_experiment_json(args.plan)
    allocation = load_experiment_json(args.allocation)
    case = load_experiment_json(args.case)
    commitment = materialize_allocated_bundles(
        args.repository_root,
        plan,
        allocation,
        case,
        case_sha256=sha256_label(Path(args.case).read_bytes()),
        destination_root=args.destination_root,
    )
    _write_json_exclusive(Path(args.commitment_out), commitment)
    print(pretty_bytes(commitment).decode("utf-8"), end="")


def _load_string_array_envelope(path: str | Path, field: str) -> list[str]:
    value = load_experiment_json(path)
    value = _closed(value, path=str(path), required={field})
    return _strings(value[field], f"{path}.{field}")


def _command_score(args: argparse.Namespace) -> None:
    answer_path = Path(args.answer)
    gold_path = Path(args.gold)
    case_path = Path(args.case)
    answer = load_experiment_json(answer_path)
    gold = load_experiment_json(gold_path)
    case = load_experiment_json(case_path)
    plan = load_experiment_json(args.plan)
    validate_plan(plan)
    validate_case(case)
    case_sha256 = sha256_label(case_path.read_bytes())
    gold_sha256 = sha256_label(gold_path.read_bytes())
    expected = {item["case_id"]: item for item in plan["case_digests"]}.get(
        case["case_id"]
    )
    if expected is None:
        raise ValidationError("score case is absent from the plan")
    if expected["case_sha256"] != case_sha256:
        raise ValidationError("score case digest differs from the plan")
    if expected["gold_sha256"] != gold_sha256:
        raise ValidationError("score gold digest differs from the plan")
    if case["gold_sha256"] != gold_sha256:
        raise ValidationError("case metadata binds another gold file")
    scorer_identity = plan["model_policy"].get("scorer_identity")
    scorer_version = plan["model_policy"].get("scorer_version")
    if not scorer_identity or not scorer_version:
        raise ValidationError("plan does not pin scorer identity and version")
    score = score_trial_answer(
        answer,
        gold,
        answer_sha256=sha256_label(answer_path.read_bytes()),
        case_id=case["case_id"],
        case_sha256=case_sha256,
        gold_sha256=gold_sha256,
        observed_actions=_load_string_array_envelope(
            args.observed_actions,
            "observed_actions",
        ),
        plan_id=plan["plan_id"],
        scored_at=args.scored_at,
        scorer_identity=scorer_identity,
        scorer_version=scorer_version,
    )
    expected_scorer_sha256 = plan["model_policy"].get("scorer_sha256")
    if (
        expected_scorer_sha256 is not None
        and score["scorer_sha256"] != expected_scorer_sha256
    ):
        raise ValidationError("running scorer differs from the pinned scorer")
    _write_json_exclusive(Path(args.output), score)
    print(pretty_bytes(score).decode("utf-8"), end="")


def _command_run_receipt(args: argparse.Namespace) -> None:
    plan = load_experiment_json(args.plan)
    bundle = load_experiment_json(args.bundle)
    validate_plan(plan)
    if bundle["schema_version"] != BUNDLE_VERSION:
        raise ValidationError("unsupported experiment bundle version")
    _validate_identity(bundle, "bundle_id", "bundle")
    observed_actions = _load_string_array_envelope(
        args.observed_actions,
        "observed_actions",
    )
    notes = _load_string_array_envelope(args.notes, "notes")
    receipt = make_run_receipt(
        plan_id=plan["plan_id"],
        trial_id=bundle["trial_id"],
        bundle_id=bundle["bundle_id"],
        answer_sha256=sha256_label(Path(args.answer).read_bytes()),
        trace_sha256=sha256_label(Path(args.trace).read_bytes()),
        started_at=args.started_at,
        finished_at=args.finished_at,
        model=args.model,
        termination=args.termination,
        observed_actions=observed_actions,
        notes=notes,
    )
    _write_json_exclusive(Path(args.output), receipt)
    print(pretty_bytes(receipt).decode("utf-8"), end="")


def _command_audit(args: argparse.Namespace) -> None:
    plan = load_experiment_json(args.plan)
    allocation = load_experiment_json(args.allocation)
    runs = [load_experiment_json(path) for path in args.run]
    scores = [load_experiment_json(path) for path in args.score]
    commitment = (
        load_experiment_json(args.bundle_commitment) if args.bundle_commitment else None
    )
    audit = audit_study_completeness(
        plan,
        allocation,
        runs,
        scores,
        bundle_commitment=commitment,
    )
    _write_json_exclusive(Path(args.output), audit)
    print(pretty_bytes(audit).decode("utf-8"), end="")


def _command_validate_answer(args: argparse.Namespace) -> None:
    answer = load_experiment_json(args.answer)
    validate_trial_answer(answer, trial_id=args.trial_id)
    print(
        pretty_bytes(
            {
                "answer_sha256": sha256_label(Path(args.answer).read_bytes()),
                "schema_version": ANSWER_VERSION,
                "trial_id": answer["trial_id"],
                "valid": True,
            }
        ).decode("utf-8"),
        end="",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and score offline ClaimPack cold-agent experiments"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--template", required=True)
    prepare.add_argument("--seed-file", required=True)
    prepare.add_argument("--plan-out", required=True)
    prepare.add_argument("--allocation-out", required=True)
    prepare.set_defaults(handler=_command_prepare)
    bundle = subparsers.add_parser("bundle")
    bundle.add_argument("--repository-root", required=True)
    bundle.add_argument("--case", required=True)
    bundle.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    bundle.add_argument("--trial-id", required=True)
    bundle.add_argument("--destination", required=True)
    bundle.set_defaults(handler=_command_bundle)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--repository-root", required=True)
    materialize.add_argument("--plan", required=True)
    materialize.add_argument("--allocation", required=True)
    materialize.add_argument("--case", required=True)
    materialize.add_argument("--destination-root", required=True)
    materialize.add_argument("--commitment-out", required=True)
    materialize.set_defaults(handler=_command_materialize)
    score = subparsers.add_parser("score")
    score.add_argument("--answer", required=True)
    score.add_argument("--gold", required=True)
    score.add_argument("--case", required=True)
    score.add_argument("--plan", required=True)
    score.add_argument("--observed-actions", required=True)
    score.add_argument("--scored-at", required=True)
    score.add_argument("--output", required=True)
    score.set_defaults(handler=_command_score)
    run_receipt = subparsers.add_parser("run-receipt")
    run_receipt.add_argument("--plan", required=True)
    run_receipt.add_argument("--bundle", required=True)
    run_receipt.add_argument("--answer", required=True)
    run_receipt.add_argument("--trace", required=True)
    run_receipt.add_argument("--started-at", required=True)
    run_receipt.add_argument("--finished-at", required=True)
    run_receipt.add_argument("--model", required=True)
    run_receipt.add_argument(
        "--termination",
        choices=["completed", "error", "timeout", "invalid-output"],
        required=True,
    )
    run_receipt.add_argument("--observed-actions", required=True)
    run_receipt.add_argument("--notes", required=True)
    run_receipt.add_argument("--output", required=True)
    run_receipt.set_defaults(handler=_command_run_receipt)
    audit = subparsers.add_parser("audit")
    audit.add_argument("--plan", required=True)
    audit.add_argument("--allocation", required=True)
    audit.add_argument("--bundle-commitment")
    audit.add_argument("--run", action="append", default=[], required=True)
    audit.add_argument("--score", action="append", default=[])
    audit.add_argument("--output", required=True)
    audit.set_defaults(handler=_command_audit)
    validate_answer = subparsers.add_parser("validate-answer")
    validate_answer.add_argument("--answer", required=True)
    validate_answer.add_argument("--trial-id")
    validate_answer.set_defaults(handler=_command_validate_answer)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except (OSError, ValidationError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate the pinned VR2 cold-agent case metadata and catalogue projection."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from claimpack.canonical import canonical_bytes, pretty_bytes, strict_loads
from claimpack.experiment import (
    CASE_VERSION,
    TRIAL_ID_SCHEMA_PLACEHOLDER,
    validate_case,
)
from claimpack.ids import ni_sha256, sha256_label

CASE_ROOT = Path("evaluation/cases/C001-vr2-k4")
BASE_ARCHIVE = CASE_ROOT / "source/base-release-b303d7d.tar.gz"
BASE_ARCHIVE_SHA256 = (
    "sha256:c8ecfb13541ef1dad7016b00fbdcbf676f797451317adb28d7f93c9e30e04996"
)
VR2_CLAIM_ID = "ni:///sha-256;cDwAiv3p8UiaXGlcLfx5Ef_2Kgf1NM3j9XhkxGxFkis"
FIXED_CORE_CLAIM_ID = "ni:///sha-256;XZiVDafrILfPSxDvR1kHHCr5Cfk_gEKmC-WAOzVi9xg"
PROVIDER_UNSUPPORTED_SCHEMA_KEYS = {
    "maxItems",
    "maxLength",
    "minItems",
    "minLength",
    "pattern",
    "uniqueItems",
}


def _digest(path: Path) -> str:
    return sha256_label(path.read_bytes())


def _entry(
    repository_root: Path,
    source: str,
    destination: str,
) -> dict[str, str]:
    return {
        "destination": destination,
        "sha256": _digest(repository_root / source),
        "source": source,
    }


def _provider_schema_projection(value: object) -> object:
    if isinstance(value, list):
        return [_provider_schema_projection(item) for item in value]
    if not isinstance(value, dict):
        return value
    projected = {
        key: _provider_schema_projection(item)
        for key, item in value.items()
        if key not in PROVIDER_UNSUPPORTED_SCHEMA_KEYS
    }
    if "type" not in projected:
        candidates = projected.get("enum")
        if (
            isinstance(candidates, list)
            and candidates
            and all(isinstance(item, str) for item in candidates)
        ):
            projected["type"] = "string"
        elif isinstance(projected.get("const"), str):
            projected["type"] = "string"
    return projected


def _generate_provider_schemas(
    repository_root: Path,
    output_root: Path,
) -> tuple[Path, Path]:
    source = json.loads(
        (
            repository_root / "evaluation/schemas/trial-answer-v0.1.schema.json"
        ).read_text(encoding="utf-8")
    )
    projection = _provider_schema_projection(source)
    if not isinstance(projection, dict):
        raise RuntimeError("provider schema projection must be an object")
    projection["$id"] = (
        "https://example.invalid/claimpack/trial-answer-provider-v0.1.schema.json"
    )
    projection["title"] = "ClaimPack provider-compatible arm-neutral TrialAnswer v0.1"
    v1_path = output_root / "evaluation/schemas/trial-answer-provider-v0.1.schema.json"
    v1_path.parent.mkdir(parents=True, exist_ok=True)
    v1_path.write_bytes(pretty_bytes(projection))

    bound_projection = deepcopy(projection)
    bound_projection["$id"] = (
        "https://example.invalid/claimpack/trial-answer-provider-v0.2.schema.json"
    )
    bound_projection["title"] = (
        "ClaimPack provider-compatible, trial-bound TrialAnswer v0.2"
    )
    trial_schema = bound_projection["properties"]["trial_id"]
    trial_schema["const"] = TRIAL_ID_SCHEMA_PLACEHOLDER
    trial_schema["type"] = "string"
    v2_path = output_root / "evaluation/schemas/trial-answer-provider-v0.2.schema.json"
    v2_path.write_bytes(pretty_bytes(bound_projection))
    return v1_path, v2_path


def _catalogue_projection(repository_root: Path) -> dict:
    source = strict_loads((repository_root / "catalog/catalog.json").read_bytes())
    projection = {
        "catalog_head": "",
        "entries": [
            deepcopy(entry)
            for entry in source["entries"]
            if entry["claim_id"] in {VR2_CLAIM_ID, FIXED_CORE_CLAIM_ID}
        ],
        "generated_at": source["generated_at"],
        "schema_version": source["schema_version"],
        "search_fingerprint_profile": source["search_fingerprint_profile"],
    }
    projection["catalog_head"] = ni_sha256(
        canonical_bytes(
            {key: value for key, value in projection.items() if key != "catalog_head"}
        )
    )
    return projection


def generate(repository_root: Path, output_root: Path) -> list[Path]:
    repository_root = repository_root.resolve()
    output_root = output_root.resolve()
    generated_case_root = output_root / CASE_ROOT
    overlay_root = generated_case_root / "overlay"
    overlay_root.mkdir(parents=True, exist_ok=True)
    provider_schema_path, bound_provider_schema_path = _generate_provider_schemas(
        repository_root,
        output_root,
    )

    catalogue_path = overlay_root / "STATIC_CATALOG.json"
    catalogue_path.write_bytes(pretty_bytes(_catalogue_projection(repository_root)))

    common_files = [
        _entry(
            repository_root,
            "evaluation/prompts/consumer-task-v0.1.md",
            "TASK.md",
        ),
        _entry(
            repository_root,
            "evaluation/schemas/trial-answer-v0.1.schema.json",
            "RESPONSE_SCHEMA.json",
        ),
        _entry(
            repository_root,
            f"{CASE_ROOT.as_posix()}/common/SOURCE_IDENTITY.json",
            "MATERIALS/evaluator/SOURCE_IDENTITY.json",
        ),
        _entry(
            repository_root,
            f"{CASE_ROOT.as_posix()}/common/DECISION_POLICY.md",
            "MATERIALS/evaluator/DECISION_POLICY.md",
        ),
        _entry(
            repository_root,
            f"{CASE_ROOT.as_posix()}/common/UNTRUSTED_CANARY.md",
            "MATERIALS/evaluator/UNTRUSTED_CANARY.md",
        ),
    ]

    overlay_files = [
        _entry(
            repository_root,
            "SKILL.md",
            "MATERIALS/supplement/CONSUMER_SKILL.md",
        ),
        _entry(
            repository_root,
            "policies/cautious-scientific-use-v0.1.json",
            "MATERIALS/supplement/CAUTIOUS_POLICY.json",
        ),
        {
            "destination": "MATERIALS/supplement/STATIC_CATALOG.json",
            "sha256": _digest(catalogue_path),
            "source": f"{CASE_ROOT.as_posix()}/overlay/STATIC_CATALOG.json",
        },
    ]
    pack_root = repository_root / "examples/vr2-k4"
    for path in sorted(pack_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(pack_root).as_posix()
        overlay_files.append(
            _entry(
                repository_root,
                f"examples/vr2-k4/{relative}",
                f"MATERIALS/supplement/claimpack/{relative}",
            )
        )

    fixed_sources = [
        "MATERIALS/release/AI_INDEX.md",
        "MATERIALS/release/README.md",
        "MATERIALS/release/certificates/README.md",
        "MATERIALS/release/certificates/results.txt",
        "MATERIALS/release/paper/z20_equals_6_replay_receipt_2026-07-26.md",
    ]
    vr2_sources = [
        "MATERIALS/release/applications/vr2-k4/AI_INDEX.md",
        "MATERIALS/release/applications/vr2-k4/README.md",
        "MATERIALS/release/applications/vr2-k4/UPSTREAM_Z20.md",
        "MATERIALS/release/applications/vr2-k4/paper.tex",
    ]
    overlay_provenance = [
        {
            "base_sources": vr2_sources + fixed_sources,
            "overlay_path": "MATERIALS/supplement/STATIC_CATALOG.json",
            "scope": "Two-entry discovery projection; no new scientific fact.",
        }
    ]
    for item in overlay_files:
        destination = item["destination"]
        if "/claimpack/records/" not in destination:
            continue
        filename = destination.rsplit("/", 1)[-1]
        index = int(filename.split("-", 1)[0])
        if index <= 14:
            sources = fixed_sources
            scope = "Fixed-core claim, evidence, or producer assessment."
        elif index in {16, 17}:
            sources = vr2_sources + fixed_sources
            scope = "VR2-to-fixed-core dependency or correspondence assessment."
        else:
            sources = vr2_sources
            scope = "VR2 claim, evidence, or producer assessment."
        overlay_provenance.append(
            {
                "base_sources": sources,
                "overlay_path": destination,
                "scope": scope,
            }
        )

    archive_path = repository_root / BASE_ARCHIVE
    if _digest(archive_path) != BASE_ARCHIVE_SHA256:
        raise RuntimeError("pinned base archive digest changed")
    gold_path = repository_root / CASE_ROOT / "gold.json"
    case = {
        "base_archive": {
            "format": "tar.gz",
            "path": BASE_ARCHIVE.as_posix(),
            "sha256": BASE_ARCHIVE_SHA256,
        },
        "case_id": "C001-vr2-k4-candidate",
        "common_files": common_files,
        "gold_sha256": _digest(gold_path),
        "overlay_files": overlay_files,
        "overlay_provenance": overlay_provenance,
        "schema_version": CASE_VERSION,
    }
    validate_case(case)
    case_path = generated_case_root / "case.json"
    case_path.write_bytes(pretty_bytes(case))

    provider_case = deepcopy(case)
    provider_case["case_id"] = "C001-vr2-k4-candidate-provider-v2"
    response_schema = next(
        item
        for item in provider_case["common_files"]
        if item["destination"] == "RESPONSE_SCHEMA.json"
    )
    response_schema["source"] = (
        "evaluation/schemas/trial-answer-provider-v0.1.schema.json"
    )
    response_schema["sha256"] = _digest(provider_schema_path)
    validate_case(provider_case)
    provider_case_path = generated_case_root / "case-provider-v2.json"
    provider_case_path.write_bytes(pretty_bytes(provider_case))

    bound_provider_case = deepcopy(provider_case)
    bound_provider_case["case_id"] = "C001-vr2-k4-candidate-provider-v3"
    response_schema = next(
        item
        for item in bound_provider_case["common_files"]
        if item["destination"] == "RESPONSE_SCHEMA.json"
    )
    response_schema["source"] = (
        "evaluation/schemas/trial-answer-provider-v0.2.schema.json"
    )
    response_schema["sha256"] = _digest(bound_provider_schema_path)
    validate_case(bound_provider_case)
    bound_provider_case_path = generated_case_root / "case-provider-v3.json"
    bound_provider_case_path.write_bytes(pretty_bytes(bound_provider_case))
    return [
        case_path,
        provider_case_path,
        bound_provider_case_path,
        catalogue_path,
        provider_schema_path,
        bound_provider_schema_path,
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for path in generate(root, root):
        print(path.relative_to(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

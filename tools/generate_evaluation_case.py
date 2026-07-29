"""Generate the pinned VR2 cold-agent case metadata and catalogue projection."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from claimpack.canonical import canonical_bytes, pretty_bytes, strict_loads
from claimpack.experiment import CASE_VERSION, validate_case
from claimpack.ids import ni_sha256, sha256_label

CASE_ROOT = Path("evaluation/cases/C001-vr2-k4")
BASE_ARCHIVE = CASE_ROOT / "source/base-release-b303d7d.tar.gz"
BASE_ARCHIVE_SHA256 = (
    "sha256:c8ecfb13541ef1dad7016b00fbdcbf676f797451317adb28d7f93c9e30e04996"
)
VR2_CLAIM_ID = "ni:///sha-256;cDwAiv3p8UiaXGlcLfx5Ef_2Kgf1NM3j9XhkxGxFkis"
FIXED_CORE_CLAIM_ID = "ni:///sha-256;XZiVDafrILfPSxDvR1kHHCr5Cfk_gEKmC-WAOzVi9xg"


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
    return [case_path, catalogue_path]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for path in generate(root, root):
        print(path.relative_to(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

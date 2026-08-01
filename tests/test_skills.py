from __future__ import annotations

import io
import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from claimpack.canonical import strict_loads
from claimpack.validate import validate_pack
from tests.helpers import make_claim


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = (
    ROOT
    / "skills"
    / "publish-claimpack"
    / "scripts"
    / "build_minimal_pack.py"
)
BUILDER_SPEC = importlib.util.spec_from_file_location(
    "claimpack_publish_skill_builder",
    BUILDER_PATH,
)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
BUILDER_MODULE = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(BUILDER_MODULE)
build_minimal_pack = BUILDER_MODULE.main


class SkillResourceTests(unittest.TestCase):
    def test_consumer_skill_bundles_exact_cautious_policy(self) -> None:
        core = ROOT / "policies/cautious-scientific-use-v0.1.json"
        bundled = (
            ROOT
            / "skills"
            / "consume-claimpack"
            / "assets"
            / "cautious-scientific-use-v0.1.json"
        )
        self.assertEqual(
            strict_loads(core.read_bytes()),
            strict_loads(bundled.read_bytes()),
        )

    def test_minimal_builder_seals_and_validates_one_claim_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = make_claim()
            draft.pop("claim_id")
            draft.pop("record_id")
            claim_path = root / "claim.json"
            claim_path.write_text(json.dumps(draft), encoding="utf-8")
            destination = root / "pack"

            output = io.StringIO()
            with redirect_stdout(output):
                result = build_minimal_pack(
                    [
                        "--claim",
                        str(claim_path),
                        "--destination",
                        str(destination),
                        "--created-at",
                        "2026-08-01T00:00:00+00:00",
                    ]
                )

            pack = validate_pack(str(destination))
            self.assertEqual(result, 0)
            self.assertEqual(len(pack.claims()), 1)
            self.assertIn(str(destination / "claimpack.json"), output.getvalue())

    def test_minimal_builder_rejects_unchanged_template(self) -> None:
        template = (
            ROOT
            / "skills"
            / "publish-claimpack"
            / "assets"
            / "minimal-claim-version.json.example"
        )
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(SystemExit, "placeholders"):
                build_minimal_pack(
                    [
                        "--claim",
                        str(template),
                        "--destination",
                        str(Path(temporary) / "pack"),
                        "--created-at",
                        "2026-08-01T00:00:00+00:00",
                    ]
                )


if __name__ == "__main__":
    unittest.main()

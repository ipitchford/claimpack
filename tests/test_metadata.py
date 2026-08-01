from __future__ import annotations

import inspect
import json
import tomllib
import unittest
from pathlib import Path

from claimpack import __version__
from claimpack.cli import _parser
from claimpack.receipt import create_use_receipt

ROOT = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    def test_runtime_version_is_consistent(self) -> None:
        metadata = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["project"]["version"], __version__)
        self.assertEqual(
            inspect.signature(create_use_receipt)
            .parameters["consumer_version"]
            .default,
            __version__,
        )
        parsed = _parser().parse_args(
            ["decide", "pack", "--policy", "policy.json"]
        )
        self.assertEqual(parsed.consumer_version, __version__)

    def test_checked_in_json_documents_parse(self) -> None:
        paths = [
            ROOT / "badclaims/cases.json",
            ROOT / "catalog/catalog.json",
            ROOT / "evaluation/cases/C001-vr2-k4/case.json",
            ROOT / "evaluation/cases/C001-vr2-k4/case-provider-v2.json",
            ROOT / "evaluation/cases/C001-vr2-k4/case-provider-v3.json",
            ROOT / "evaluation/cases/C001-vr2-k4/common/SOURCE_IDENTITY.json",
            ROOT / "evaluation/cases/C001-vr2-k4/gold.json",
            ROOT / "evaluation/cases/C001-vr2-k4/overlay/STATIC_CATALOG.json",
            ROOT / "evaluation/preregistration/plan-template.json",
            ROOT / "evaluation/preregistration/plan.json",
            ROOT / "evaluation/preregistration/bundle-commitment.json",
            ROOT / "evaluation/preregistration/bundle-commitment-provider-v2.json",
            ROOT / "evaluation/preregistration/bundle-commitment-provider-v3.json",
            ROOT / "evaluation/preregistration/bundle-commitment-provider-v4.json",
            ROOT / "evaluation/preregistration/plan-provider-v2-template.json",
            ROOT / "evaluation/preregistration/plan-provider-v2.json",
            ROOT / "evaluation/preregistration/plan-provider-v3-template.json",
            ROOT / "evaluation/preregistration/plan-provider-v3.json",
            ROOT / "evaluation/preregistration/plan-provider-v4-template.json",
            ROOT / "evaluation/preregistration/plan-provider-v4.json",
            ROOT / "evaluation/schemas/trial-answer-v0.1.schema.json",
            ROOT / "evaluation/schemas/trial-answer-provider-v0.1.schema.json",
            ROOT / "evaluation/schemas/trial-answer-provider-v0.2.schema.json",
            ROOT / "policies/cautious-scientific-use-v0.1.json",
            *sorted((ROOT / "schemas").glob("*.json")),
        ]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                with path.open("r", encoding="utf-8") as handle:
                    self.assertIsInstance(json.load(handle), dict)

    def test_provider_schema_uses_supported_projection(self) -> None:
        unsupported = {
            "maxItems",
            "maxLength",
            "minItems",
            "minLength",
            "pattern",
            "uniqueItems",
        }

        def walk(value: object) -> None:
            if isinstance(value, dict):
                self.assertTrue(unsupported.isdisjoint(value))
                if "enum" in value or "const" in value:
                    self.assertIn("type", value)
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        for filename in {
            "trial-answer-provider-v0.1.schema.json",
            "trial-answer-provider-v0.2.schema.json",
        }:
            with self.subTest(filename=filename):
                path = ROOT / "evaluation/schemas" / filename
                with path.open("r", encoding="utf-8") as handle:
                    schema = json.load(handle)
                walk(schema)


if __name__ == "__main__":
    unittest.main()

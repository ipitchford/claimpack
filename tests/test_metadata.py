from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    def test_checked_in_json_documents_parse(self) -> None:
        paths = [
            ROOT / "badclaims/cases.json",
            ROOT / "catalog/catalog.json",
            ROOT / "evaluation/cases/C001-vr2-k4/case.json",
            ROOT / "evaluation/cases/C001-vr2-k4/common/SOURCE_IDENTITY.json",
            ROOT / "evaluation/cases/C001-vr2-k4/gold.json",
            ROOT / "evaluation/cases/C001-vr2-k4/overlay/STATIC_CATALOG.json",
            ROOT / "evaluation/preregistration/plan-template.json",
            ROOT / "evaluation/preregistration/plan.json",
            ROOT / "evaluation/schemas/trial-answer-v0.1.schema.json",
            ROOT / "policies/cautious-scientific-use-v0.1.json",
            *sorted((ROOT / "schemas").glob("*.json")),
        ]
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                with path.open("r", encoding="utf-8") as handle:
                    self.assertIsInstance(json.load(handle), dict)


if __name__ == "__main__":
    unittest.main()

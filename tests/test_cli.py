from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from claimpack.cli import main

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-07-29T13:00:00+00:00"
POLICY = ROOT / "policies/cautious-scientific-use-v0.1.json"
Z20 = ROOT / "examples/z20"


class CliTests(unittest.TestCase):
    def test_decide_without_receipt_path_is_read_only_and_prints_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            working = Path(temporary)
            before = list(working.iterdir())
            output = io.StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "decide",
                        str(Z20),
                        "--policy",
                        str(POLICY),
                        "--as-of",
                        AS_OF,
                    ]
                )
            after = list(working.iterdir())

        receipt = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(before, after)
        self.assertEqual(receipt["record_type"], "use-receipt")
        self.assertEqual(receipt["decision"], "UNKNOWN")
        self.assertEqual(receipt["executed_commands"], [])
        self.assertEqual(len(receipt["dimension_results"]), 12)
        self.assertTrue(receipt["qualifications"])

    def test_inspect_exposes_trust_boundary_and_quoted_replay(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = main(["inspect", str(Z20)])

        inspection = json.loads(output.getvalue())
        self.assertEqual(result, 0)
        self.assertTrue(inspection["evidence"])
        self.assertTrue(inspection["assessments"])
        self.assertTrue(inspection["relations"])
        self.assertTrue(any(item["limitations"] for item in inspection["evidence"]))
        self.assertTrue(
            all(item["replay"]["display_only"] for item in inspection["evidence"])
        )
        self.assertTrue(
            all(
                item["authentication"]["status"] == "unverified"
                for item in inspection["assessments"]
            )
        )

    def test_named_receipt_is_exclusive_and_summary_pins_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            receipt_path = Path(temporary) / "receipt.json"
            output = io.StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "decide",
                        str(Z20),
                        "--policy",
                        str(POLICY),
                        "--as-of",
                        AS_OF,
                        "--receipt",
                        str(receipt_path),
                    ]
                )
            summary = json.loads(output.getvalue())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

            self.assertEqual(result, 0)
            self.assertEqual(summary["receipt_record_id"], receipt["record_id"])
            self.assertEqual(summary["decision"], "UNKNOWN")

            with redirect_stdout(io.StringIO()):
                overwrite_result = main(
                    [
                        "decide",
                        str(Z20),
                        "--policy",
                        str(POLICY),
                        "--as-of",
                        AS_OF,
                        "--receipt",
                        str(receipt_path),
                    ]
                )
            self.assertEqual(overwrite_result, 2)

    def test_invalid_ledger_request_does_not_write_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            receipt_path = Path(temporary) / "must-not-exist.json"
            with redirect_stdout(io.StringIO()):
                result = main(
                    [
                        "decide",
                        str(Z20),
                        "--policy",
                        str(POLICY),
                        "--as-of",
                        AS_OF,
                        "--receipt",
                        str(receipt_path),
                        "--update-ledger",
                    ]
                )

            self.assertEqual(result, 2)
            self.assertFalse(receipt_path.exists())


if __name__ == "__main__":
    unittest.main()

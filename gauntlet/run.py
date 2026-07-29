#!/usr/bin/env python3
"""Run the named adversarial ClaimPack cases without executing pack content."""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_gauntlet import GauntletTests  # noqa: E402

CASE_ID = re.compile(r"^G[0-9]{2}$")
TEST_METHOD = re.compile(r"^test_(G[0-9]{2})(?:_|$)")


def build_suite() -> unittest.TestSuite:
    with (ROOT / "badclaims" / "cases.json").open(encoding="utf-8") as handle:
        document = json.load(handle)

    listed_ids = [case["id"] for case in document["cases"]]
    if any(
        not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id)
        for case_id in listed_ids
    ):
        raise ValueError("every badclaims case must have a Gxx identifier")
    if len(listed_ids) != len(set(listed_ids)):
        raise ValueError("badclaims/cases.json contains duplicate case identifiers")

    methods_by_id: dict[str, list[str]] = {}
    for name in unittest.defaultTestLoader.getTestCaseNames(GauntletTests):
        match = TEST_METHOD.match(name)
        if match:
            methods_by_id.setdefault(match.group(1), []).append(name)

    listed = set(listed_ids)
    implemented = set(methods_by_id)
    missing = sorted(listed - implemented)
    undocumented = sorted(implemented - listed)
    duplicate_methods = {
        case_id: names for case_id, names in methods_by_id.items() if len(names) != 1
    }
    if missing or undocumented or duplicate_methods:
        raise ValueError(
            "badclaims catalogue/test mismatch: "
            f"missing={missing}, undocumented={undocumented}, "
            f"duplicate_methods={duplicate_methods}"
        )

    suite = unittest.TestSuite()
    for case_id in listed_ids:
        suite.addTest(GauntletTests(methods_by_id[case_id][0]))
    return suite


def main() -> int:
    try:
        suite = build_suite()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"gauntlet catalogue error: {error}", file=sys.stderr)
        return 2
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

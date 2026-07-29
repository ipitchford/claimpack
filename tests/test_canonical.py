from __future__ import annotations

import unittest

from claimpack.canonical import canonical_bytes, strict_loads
from claimpack.errors import LimitError, ParseError
from claimpack.ids import ni_sha256


class CanonicalTests(unittest.TestCase):
    def test_duplicate_keys_rejected(self) -> None:
        with self.assertRaises(ParseError):
            strict_loads(b'{"a":"one","a":"two"}')

    def test_numbers_and_nonfinite_values_rejected(self) -> None:
        for value in [b'{"n":1}', b'{"n":1.5}', b'{"n":NaN}']:
            with self.subTest(value=value), self.assertRaises(ParseError):
                strict_loads(value)

    def test_invalid_utf8_rejected(self) -> None:
        with self.assertRaises(ParseError):
            strict_loads(b'{"x":"\xff"}')

    def test_deep_json_is_bounded(self) -> None:
        data = ("[" * 100_000 + "]" * 100_000).encode()
        with self.assertRaises((LimitError, ParseError)):
            strict_loads(data)

    def test_object_order_does_not_change_identity(self) -> None:
        left = {"a": "1", "b": ["2"]}
        right = {"b": ["2"], "a": "1"}
        self.assertEqual(
            ni_sha256(canonical_bytes(left)), ni_sha256(canonical_bytes(right))
        )

    def test_string_whitespace_changes_identity(self) -> None:
        self.assertNotEqual(
            ni_sha256(canonical_bytes({"x": "a b"})),
            ni_sha256(canonical_bytes({"x": "a  b"})),
        )


if __name__ == "__main__":
    unittest.main()

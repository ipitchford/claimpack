"""Regenerate evaluation metadata in isolation and compare every output byte."""

from __future__ import annotations

import tempfile
from pathlib import Path

from tools.generate_evaluation_case import generate


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        generated_root = Path(temporary).resolve()
        generated = generate(root, generated_root)
        mismatches = []
        for generated_path in generated:
            relative = generated_path.relative_to(generated_root)
            checked_in = root / relative
            if not checked_in.exists():
                mismatches.append(f"missing checked-in output: {relative}")
                continue
            if generated_path.read_bytes() != checked_in.read_bytes():
                mismatches.append(f"generated output differs: {relative}")
        if mismatches:
            raise SystemExit("\n".join(mismatches))
        print(f"generated evaluation metadata matches ({len(generated)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

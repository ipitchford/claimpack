from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from claimpack.errors import LimitError, ValidationError
from claimpack.build import write_pack
from claimpack.validate import validate_pack

from tests.helpers import demo_components, write_demo


def zip_directory(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


class ReaderTests(unittest.TestCase):
    def test_ordinary_deflated_zip_matches_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            directory = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            archive = root / "pack.zip"
            zip_directory(directory, archive)
            self.assertEqual(
                validate_pack(str(directory)).package_root,
                validate_pack(str(archive)).package_root,
            )

    def test_zip_traversal_rejected_without_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../escape", "bad")
            with self.assertRaises(ValidationError):
                validate_pack(str(archive))
            self.assertFalse((root.parent / "escape").exists())

    def test_fifo_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, artifacts = demo_components()
            directory = write_demo(
                root / "pack",
                claim=claim,
                evidence=evidence,
                assessments=assessments,
                artifacts=artifacts,
            )
            os.mkfifo(directory / "undeclared-fifo")
            with self.assertRaises(ValidationError):
                validate_pack(str(directory))

    def test_compression_ratio_bomb_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "bomb.zip"
            with zipfile.ZipFile(
                archive, "w", compression=zipfile.ZIP_DEFLATED
            ) as handle:
                handle.writestr("claimpack.json", b"0" * 1_000_000)
            with self.assertRaises(LimitError):
                validate_pack(str(archive))

    def test_producer_rejects_artifact_traversal_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim, evidence, assessments, _ = demo_components()
            with self.assertRaises(ValidationError):
                write_pack(
                    root / "pack",
                    records=[claim, evidence, *assessments],
                    artifacts={"../escape": (b"bad", "text/plain")},
                    created_at="2026-07-29T00:00:00+00:00",
                    primary_claim_record_id=claim["record_id"],
                )
            self.assertFalse((root / "pack").exists())
            self.assertFalse((root.parent / "escape").exists())


if __name__ == "__main__":
    unittest.main()

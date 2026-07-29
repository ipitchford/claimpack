"""Bounded, non-extracting ClaimPack directory and ZIP reader."""

from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path, PurePosixPath

from .errors import LimitError, ValidationError

MAX_FILES = 2_048
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def validate_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError("package path must be a non-empty string")
    if "\\" in value or "\x00" in value:
        raise ValidationError(f"unsafe package path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError(f"unsafe package path: {value!r}")
    return path.as_posix()


class PackReader:
    """Read selected files without network access, imports, or extraction."""

    def __init__(self, source: str | Path) -> None:
        self.source = Path(source)
        self._zip: zipfile.ZipFile | None = None
        self._zip_entries: dict[str, zipfile.ZipInfo] = {}
        self._root_fd: int | None = None
        self._total_read_bytes = 0

        if self.source.is_dir():
            self.kind = "directory"
            self.root = self.source.resolve(strict=True)
            try:
                self._root_fd = os.open(
                    self.root,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                )
            except OSError as exc:
                raise ValidationError("cannot safely open package directory") from exc
        elif self.source.is_file() and zipfile.is_zipfile(self.source):
            if self.source.stat().st_size > MAX_ARCHIVE_BYTES:
                raise LimitError("ZIP archive exceeds compressed-size limit")
            self.kind = "zip"
            self.root = None
            try:
                self._zip = zipfile.ZipFile(self.source, "r")
                self._validate_zip_inventory()
            except (NotImplementedError, RuntimeError, zipfile.BadZipFile) as exc:
                if self._zip is not None:
                    self._zip.close()
                self._zip = None
                raise ValidationError("malformed or unsupported ZIP archive") from exc
            except Exception:
                if self._zip is not None:
                    self._zip.close()
                self._zip = None
                raise
        else:
            raise ValidationError("pack must be a directory or ZIP archive")

    def __enter__(self) -> "PackReader":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None
        if self._root_fd is not None:
            os.close(self._root_fd)
            self._root_fd = None

    def _validate_zip_inventory(self) -> None:
        assert self._zip is not None
        entries: dict[str, zipfile.ZipInfo] = {}
        total = 0
        for entry_count, info in enumerate(self._zip.infolist(), start=1):
            if entry_count > MAX_FILES:
                raise LimitError("ZIP entry count exceeds limit")
            name = validate_relative_path(info.filename.rstrip("/"))
            if info.flag_bits & 0x1:
                raise ValidationError(f"encrypted ZIP member is forbidden: {name}")
            mode = info.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            if info.is_dir():
                if info.file_size or (file_type and file_type != stat.S_IFDIR):
                    raise ValidationError(
                        f"invalid ZIP directory entry is forbidden: {name}"
                    )
                continue
            if name in entries:
                raise ValidationError(f"duplicate ZIP path: {name}")
            if file_type and file_type != stat.S_IFREG:
                raise ValidationError(f"non-regular ZIP member is forbidden: {name}")
            if info.file_size > MAX_FILE_BYTES:
                raise LimitError(f"ZIP member exceeds size limit: {name}")
            if info.file_size and info.compress_size == 0:
                raise LimitError(f"invalid compression metadata: {name}")
            if (
                info.compress_size
                and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise LimitError(f"ZIP compression ratio exceeds limit: {name}")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise LimitError("ZIP total uncompressed size exceeds limit")
            entries[name] = info
        self._zip_entries = entries

    def list_files(self) -> list[str]:
        if self.kind == "zip":
            return sorted(self._zip_entries)

        assert self.root is not None
        files: list[str] = []
        total = 0
        for entry_count, candidate in enumerate(self.root.rglob("*"), start=1):
            if entry_count > MAX_FILES:
                raise LimitError("package entry count exceeds limit")
            metadata = candidate.lstat()
            mode = metadata.st_mode
            if stat.S_ISLNK(mode):
                raise ValidationError(
                    f"symlink is forbidden in package: {candidate.relative_to(self.root)}"
                )
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ValidationError(
                    "non-regular entry is forbidden in package: "
                    f"{candidate.relative_to(self.root)}"
                )
            relative = candidate.relative_to(self.root).as_posix()
            validate_relative_path(relative)
            size = metadata.st_size
            if size > MAX_FILE_BYTES:
                raise LimitError(f"file exceeds size limit: {relative}")
            total += size
            if total > MAX_TOTAL_BYTES:
                raise LimitError("package total size exceeds limit")
            files.append(relative)
        return sorted(files)

    def _read_directory_member(self, relative: str, max_bytes: int) -> bytes:
        """Open every path component relative to a pinned root descriptor."""

        assert self._root_fd is not None
        relative = validate_relative_path(relative)
        components = PurePosixPath(relative).parts
        directory_fd = os.dup(self._root_fd)
        member_fd: int | None = None
        try:
            for component in components[:-1]:
                next_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                os.close(directory_fd)
                directory_fd = next_fd
            member_fd = os.open(
                components[-1],
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            metadata = os.fstat(member_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValidationError(f"package path is not a regular file: {relative}")
            if metadata.st_size > max_bytes:
                raise LimitError(f"file exceeds read limit: {relative}")
            chunks: list[bytes] = []
            remaining = max_bytes + 1
            while remaining:
                chunk = os.read(member_fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            if len(data) > max_bytes:
                raise LimitError(f"file expanded beyond read limit: {relative}")
            return data
        except FileNotFoundError as exc:
            raise ValidationError(f"missing package file: {relative}") from exc
        except OSError as exc:
            raise ValidationError(
                f"cannot safely open package file: {relative}"
            ) from exc
        finally:
            if member_fd is not None:
                os.close(member_fd)
            os.close(directory_fd)

    def read_bytes(self, relative: str, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
        relative = validate_relative_path(relative)
        if self.kind == "directory":
            data = self._read_directory_member(relative, max_bytes)
            self._account_read(len(data))
            return data

        info = self._zip_entries.get(relative)
        if info is None:
            raise ValidationError(f"missing ZIP member: {relative}")
        if info.file_size > max_bytes:
            raise LimitError(f"ZIP member exceeds read limit: {relative}")
        assert self._zip is not None
        try:
            with self._zip.open(info, "r") as handle:
                data = handle.read(max_bytes + 1)
        except (NotImplementedError, RuntimeError, zipfile.BadZipFile) as exc:
            raise ValidationError(
                f"malformed or unsupported ZIP member: {relative}"
            ) from exc
        if len(data) > max_bytes:
            raise LimitError(f"ZIP member expanded beyond read limit: {relative}")
        self._account_read(len(data))
        return data

    def _account_read(self, size: int) -> None:
        self._total_read_bytes += size
        if self._total_read_bytes > MAX_TOTAL_BYTES:
            raise LimitError("package bytes read exceed total limit")

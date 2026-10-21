"""Verified cleanup of the old development file storage that a database reset would orphan.

The app keeps uploads under ``<backend>/.data/object_storage`` as ``<app>/tenants/<tenant>/files/<uuid>.<ext>`` (plus
legacy ``tests/<tenant>/...`` keys written by tests before they were isolated). After ``signguy_local`` is dropped none of
those files is referenced by any record.

``plan`` is read-only. ``execute`` removes files only when ALL of these hold for every file:
  * the directory is exactly a ``<backend>/.data/object_storage`` folder;
  * every key sits under ``signguy-ai/tenants/`` or ``tests/`` (anything else aborts - it might be shared);
  * an identical copy (same size and sha256) exists in the matching backup folder.
Only files are deleted, then directories that became empty; the storage root itself and everything outside it stay.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_PREFIXES = ("signguy-ai/tenants/", "tests/")


class StorageCleanupError(RuntimeError):
    pass


@dataclass
class StoragePlan:
    source: Path
    backup: Path
    files: list[str] = field(default_factory=list)
    total_bytes: int = 0
    unexpected: list[str] = field(default_factory=list)
    unbacked: list[str] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return not self.unexpected and not self.unbacked

    def summary(self) -> str:
        by_area = {}
        for key in self.files:
            area = "tests/*" if key.startswith("tests/") else "signguy-ai/tenants/*"
            by_area[area] = by_area.get(area, 0) + 1
        return (f"{self.source}: {len(self.files)} files, {self.total_bytes / 1e6:.1f} MB {by_area}; "
                f"unexpected keys: {len(self.unexpected)}, missing/different in backup: {len(self.unbacked)} -> "
                f"{'SAFE to remove' if self.safe else 'NOT SAFE'}")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_root(path: Path) -> Path:
    path = path.resolve()
    if path.parts[-2:] != (".data", "object_storage") or not path.is_dir():
        raise StorageCleanupError(f"{path} is not a <backend>/.data/object_storage directory")
    return path


def plan(spec: str) -> StoragePlan:
    """``spec`` is ``<object_storage dir>=<identical backup dir>``."""
    if "=" not in spec:
        raise StorageCleanupError("use --clear-storage <object_storage dir>=<backup copy of it>")
    src, bak = (Path(p) for p in spec.split("=", 1))
    source, backup = check_root(src), Path(bak).resolve()
    if not backup.is_dir():
        raise StorageCleanupError(f"backup folder not found: {backup}")
    if backup == source or source in backup.parents or backup in source.parents:
        raise StorageCleanupError("the backup must be a separate folder outside the storage directory")
    out = StoragePlan(source, backup)
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        key = path.relative_to(source).as_posix()
        out.files.append(key)
        out.total_bytes += path.stat().st_size
        if not key.startswith(ALLOWED_PREFIXES):
            out.unexpected.append(key)
            continue
        copy = backup / key
        if not copy.is_file() or copy.stat().st_size != path.stat().st_size or _sha(copy) != _sha(path):
            out.unbacked.append(key)
    return out


def execute(p: StoragePlan) -> int:
    if not p.safe:
        raise StorageCleanupError("refusing to delete: " + p.summary())
    for key in p.files:
        (p.source / key).unlink()
    for directory in sorted((d for d in p.source.rglob("*") if d.is_dir()), key=lambda d: len(d.parts), reverse=True):
        if not any(directory.iterdir()):
            directory.rmdir()
    return len(p.files)

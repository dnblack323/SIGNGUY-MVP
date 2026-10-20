"""Developer-only demo-shop tool.

    python -m scripts.demo_shop seed                       idempotent; creates the demo shop data
    python -m scripts.demo_shop verify                     read-only checks that the demo data is complete and coherent
    python -m scripts.demo_shop storage-plan --clear-storage DIR=BACKUP   read-only: what old uploads a reset would orphan
    python -m scripts.demo_shop reset --confirm signguy_local [--clear-storage DIR=BACKUP]   drop signguy_local, empty verified old
                                                           storage, then seed (destructive)
    python -m scripts.demo_shop seed --disposable          seed a `tests._test_env run` database (for verification)

Targets exactly one database (see guard.py). No public endpoint calls this; there is no HTTP reset.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.demo_shop.guard import UnsafeDemoTargetError, resolve_target  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.demo_shop")
    ap.add_argument("command", choices=["seed", "reset", "status", "verify", "storage-plan"])
    ap.add_argument("--confirm", help="reset only: must equal the database name being dropped")
    ap.add_argument("--disposable", action="store_true", help="target the active disposable test environment instead of signguy_local")
    ap.add_argument("--env-file", help="development .env to read (default: backend/.env of this checkout)")
    ap.add_argument("--storage-path", help="<backend>/.data/object_storage the running app reads files from (default: this checkout's)")
    ap.add_argument("--clear-storage", action="append", default=[], metavar="DIR=BACKUP",
                    help="reset/storage-plan: old <backend>/.data/object_storage folder to empty, paired with its identical backup copy (repeatable)")
    args = ap.parse_args(argv)
    try:
        target = resolve_target(disposable=args.disposable, env_file=args.env_file, storage_path=args.storage_path)
    except UnsafeDemoTargetError as exc:
        sys.stderr.write(f"REFUSING TO RUN: {exc}\n")
        return 2
    from scripts.demo_shop import runner  # imported only after the target is verified

    try:
        return asyncio.run(runner.run(args.command, target, confirm=args.confirm, clear_storage=args.clear_storage))
    except UnsafeDemoTargetError as exc:
        sys.stderr.write(f"REFUSING TO RUN: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

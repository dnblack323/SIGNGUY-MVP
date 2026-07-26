"""Guarded Platform Creator bootstrap utility.

Usage:
  python backend/scripts/bootstrap_platform_creator.py assign --email person@example.com --confirm-email person@example.com --reason "Owner approval"
  python backend/scripts/bootstrap_platform_creator.py remove --email person@example.com --confirm-email person@example.com --reason "Owner approval"

This script refuses to run unless ALLOW_PLATFORM_CREATOR_BOOTSTRAP=true.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.platform_creator import (  # noqa: E402
    PlatformCreatorError,
    assign_platform_creator_by_email,
    normalize_email,
    remove_platform_creator_by_email,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assign or remove the Platform Creator role.")
    parser.add_argument("action", choices=("assign", "remove"))
    parser.add_argument("--email", required=True)
    parser.add_argument("--confirm-email", required=True)
    parser.add_argument("--reason", required=True)
    return parser.parse_args()


async def _run() -> int:
    if os.getenv("ALLOW_PLATFORM_CREATOR_BOOTSTRAP", "").lower() != "true":
        print("Refusing to run: set ALLOW_PLATFORM_CREATOR_BOOTSTRAP=true for this explicit admin action.")
        return 2
    args = _parse_args()
    try:
        target_email = normalize_email(args.email)
        confirm_email = normalize_email(args.confirm_email)
    except PlatformCreatorError as exc:
        print(f"{exc.code}: {exc.detail}")
        return 2
    if target_email != confirm_email:
        print("Refusing to run: --email and --confirm-email must match after normalization.")
        return 2
    try:
        if args.action == "assign":
            result = await assign_platform_creator_by_email(
                actor_user=None,
                email=target_email,
                reason=args.reason,
                allow_system_bootstrap=True,
                context={"source": "bootstrap_script"},
            )
        else:
            result = await remove_platform_creator_by_email(
                actor_user=None,
                email=target_email,
                reason=args.reason,
                allow_system_bootstrap=True,
                context={"source": "bootstrap_script"},
            )
    except PlatformCreatorError as exc:
        print(f"{exc.code}: {exc.detail}")
        return 1
    print(f"{args.action} complete; changed={result['changed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))

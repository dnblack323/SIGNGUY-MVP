"""Guarded local/deployment bootstrap for PLATFORM_CREATOR.

This script is intentionally not wired to any public route. It refuses to run
in production unless ALLOW_PLATFORM_CREATOR_BOOTSTRAP=true is set by the
deployment operator.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.platform_creator import (  # noqa: E402
    PLATFORM_CREATOR_EMAIL,
    assign_platform_creator_by_email,
)


async def main() -> int:
    settings = get_settings()
    allow = os.environ.get("ALLOW_PLATFORM_CREATOR_BOOTSTRAP", "false").lower() == "true"
    if settings.env == "production" and not allow:
        print("Refusing production PLATFORM_CREATOR bootstrap without ALLOW_PLATFORM_CREATOR_BOOTSTRAP=true")
        return 2

    email = os.environ.get("PLATFORM_CREATOR_BOOTSTRAP_EMAIL", PLATFORM_CREATOR_EMAIL)
    reason = os.environ.get("PLATFORM_CREATOR_BOOTSTRAP_REASON", "owner-approved security correction checkpoint")
    user = await assign_platform_creator_by_email(
        actor_user=None,
        email=email,
        allow_system_bootstrap=True,
        reason=reason,
    )
    print(f"Assigned PLATFORM_CREATOR to existing user {user['id']} ({user['email']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

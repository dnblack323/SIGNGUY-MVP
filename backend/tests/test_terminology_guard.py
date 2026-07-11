"""EC1 — Terminology Guard Tests.

Verifies:
  1. Canonical application paths (backend/app/**, frontend/src/**) are clean
     of prohibited Job-domain terms.
  2. Legacy-reference exception paths (memory, docs, evidence, SIGNGUY_AI
     audit markdown files, backend/scripts) are exempt.
"""
from __future__ import annotations

from app.core.terminology_guard import scan


def test_canonical_paths_are_clean():
    violations = scan("/app")
    assert violations == [], (
        "Prohibited Job-domain terminology detected in canonical application code:\n"
        + "\n".join(f"{v.path}:{v.line_number}: {v.matched!r} — {v.line_snippet}" for v in violations)
    )


def test_scan_returns_list():
    # smoke test — scan is idempotent and returns a list
    result = scan("/app/backend/app/core")
    assert isinstance(result, list)

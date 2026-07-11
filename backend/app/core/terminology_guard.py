"""EC1 — Canonical Terminology Guard.

Prohibits the following prohibited terms from appearing in NEW canonical
application code paths:
    Job, Job Item, Job Ticket, Production Ticket, Job Ticket Summary
    job_id, job_item_id, job_ticket_id, production_ticket_id
    /jobs, /job-tickets, /production-tickets
    class Job, class JobItem, class JobTicket, class ProductionTicket

Canonical paths that must remain clean:
    backend/app/models
    backend/app/routers
    backend/app/services
    backend/app/repositories
    frontend/src/pages
    frontend/src/components (excluding /ui shadcn)
    frontend/src/lib

Legacy-reference exception paths (guard permits prohibited terms here):
    /app/memory
    /app/docs
    /app/evidence
    /app/preflight
    /app/SIGNGUY_AI_*.md  (historical audit/migration documents)
    /app/plan.md
    /app/PRICING_DEFAULTS_AUDIT.md
    /app/README.md
    /app/design_guidelines.md
    /app/backend/tests  (may reference historical terms in test docstrings)
    /app/frontend/src/components/ui  (shadcn upstream)
    /app/backend/scripts  (migration scripts may name legacy fields)
    node_modules, __pycache__, .git, .emergent

Usage:
    python -m app.core.terminology_guard /app
    from app.core.terminology_guard import scan; violations = scan("/app")
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

PROHIBITED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bJob\s*Ticket\s*Summary\b"),
    re.compile(r"\bJob\s*Ticket\b"),
    re.compile(r"\bProduction\s*Ticket\b"),
    re.compile(r"\bJob\s*Item\b"),
    re.compile(r"\bjob_ticket_id\b"),
    re.compile(r"\bproduction_ticket_id\b"),
    re.compile(r"\bjob_item_id\b"),
    re.compile(r"\bjob_id\b"),
    re.compile(r"/jobs\b"),
    re.compile(r"/job-tickets\b"),
    re.compile(r"/production-tickets\b"),
    re.compile(r"\bclass\s+Job\b"),
    re.compile(r"\bclass\s+JobItem\b"),
    re.compile(r"\bclass\s+JobTicket\b"),
    re.compile(r"\bclass\s+ProductionTicket\b"),
)

# Directories inside /app that MUST remain clean of the prohibited terms.
CANONICAL_PATHS = (
    "backend/app/models",
    "backend/app/routers",
    "backend/app/services",
    "backend/app/repositories",
    "backend/app/core",
    "backend/server.py",
    "frontend/src/pages",
    "frontend/src/lib",
    "frontend/src/auth",
    "frontend/src/App.js",
)

# Component paths canonical EXCEPT for shadcn/ui subtree.
FRONTEND_COMPONENTS_ROOT = "frontend/src/components"
FRONTEND_UI_EXCLUDE = "frontend/src/components/ui"

# Legacy-reference exception paths (guard permits prohibited terms here).
EXCEPTIONS = (
    "/app/memory",
    "/app/docs",
    "/app/evidence",
    "/app/preflight",
    "/app/plan.md",
    "/app/README.md",
    "/app/design_guidelines.md",
    "/app/PRICING_DEFAULTS_AUDIT.md",
    "/app/backend/tests",
    "/app/backend/scripts",
    FRONTEND_UI_EXCLUDE,
    "node_modules",
    "__pycache__",
    ".git",
    ".emergent",
    ".venv",
    ".pytest_cache",
)

SIGNGUY_AUDIT_DOC_PREFIX = "/app/SIGNGUY_AI_"

TEXT_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx"}


@dataclass(frozen=True)
class TerminologyViolation:
    path: str
    line_number: int
    line_snippet: str
    matched: str


def _is_exception(path: str) -> bool:
    if path.startswith(SIGNGUY_AUDIT_DOC_PREFIX) and path.endswith(".md"):
        return True
    for ex in EXCEPTIONS:
        if ex in path:
            return True
    return False


def _is_canonical_file(path: Path) -> bool:
    p = str(path)
    if _is_exception(p):
        return False
    # Self-exception: this guard module and its tests intentionally reference
    # every prohibited term as regex patterns / documentation.
    if p.endswith("/app/core/terminology_guard.py"):
        return False
    if not path.is_file():
        return False
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    # Must live under one of the canonical roots.
    for root in CANONICAL_PATHS:
        if f"/{root}" in p or p.endswith(f"/{root}"):
            return True
    # frontend/src/components subtree except /ui.
    if FRONTEND_COMPONENTS_ROOT in p and FRONTEND_UI_EXCLUDE not in p:
        return True
    return False


def scan(base_dir: str = "/app") -> list[TerminologyViolation]:
    base = Path(base_dir)
    hits: list[TerminologyViolation] = []
    for path in base.rglob("*"):
        if not _is_canonical_file(path):
            continue
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                for pat in PROHIBITED_PATTERNS:
                    m = pat.search(line)
                    if m:
                        hits.append(
                            TerminologyViolation(
                                path=str(path),
                                line_number=line_no,
                                line_snippet=line.strip()[:200],
                                matched=m.group(0),
                            )
                        )
        except Exception:
            continue
    return hits


def format_violations(vs: Iterable[TerminologyViolation]) -> str:
    return "\n".join(f"{v.path}:{v.line_number}: matched {v.matched!r} in: {v.line_snippet}" for v in vs)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/app"
    violations = scan(root)
    if violations:
        print(format_violations(violations))
        sys.exit(1)
    print(f"terminology_guard: OK ({root})")
    sys.exit(0)

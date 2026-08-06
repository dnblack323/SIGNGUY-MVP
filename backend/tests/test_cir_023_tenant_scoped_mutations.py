from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

TENANT_OWNED_SURFACES = [
    "backend/app/routers/quotes.py",
    "backend/app/routers/orders.py",
    "backend/app/routers/invoices.py",
    "backend/app/services/documents_service.py",
    "backend/app/services/work_order_service.py",
    "backend/app/services/quote_conversion.py",
]

DB_FILTER_START = re.compile(
    r"\.(?:find_one|find_one_and_update|update_one|delete_one)\(\s*\{",
    re.MULTILINE,
)


def _first_filter(text: str, start: int) -> str:
    opening = text.find("{", start)
    assert opening >= 0
    depth = 0
    for index in range(opening, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening : index + 1]
    raise AssertionError("unclosed filter literal")


def test_tenant_owned_surfaces_do_not_mutate_or_reread_by_bare_id() -> None:
    offenders: list[str] = []
    for rel_path in TENANT_OWNED_SURFACES:
        text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        for match in DB_FILTER_START.finditer(text):
            filter_text = _first_filter(text, match.start())
            if "\"id\"" not in filter_text and "'id'" not in filter_text:
                continue
            if "\"tenant_id\"" in filter_text or "'tenant_id'" in filter_text:
                continue
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{rel_path}:{line}")

    assert offenders == []

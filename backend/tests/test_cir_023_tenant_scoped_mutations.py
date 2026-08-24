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
    "backend/app/services/production_stage_service.py",
    "backend/app/services/wrap_lab.py",
]

DB_FILTER_START = re.compile(
    r"\.(?:find_one|find_one_and_update|update_one|update_many|delete_one|replace_one)\(\s*\{",
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


def _function_body(text: str, name: str) -> str:
    match = re.search(rf"^(?:async\s+)?def {re.escape(name)}\b", text, re.MULTILINE)
    assert match, f"{name} was not found"
    next_function = re.search(r"^(?:async\s+)?def \w+\b", text[match.end() :], re.MULTILINE)
    end = match.end() + next_function.start() if next_function else len(text)
    return text[match.start() : end]


def _call_texts(text: str, marker: str) -> list[str]:
    calls: list[str] = []
    start = 0
    while True:
        index = text.find(marker, start)
        if index < 0:
            return calls
        opening = text.find("(", index)
        assert opening >= 0
        depth = 0
        for cursor in range(opening, len(text)):
            char = text[cursor]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    calls.append(text[index : cursor + 1])
                    start = cursor + 1
                    break
        else:
            raise AssertionError(f"unclosed call for {marker}")


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


def test_production_stage_history_append_is_tenant_scoped() -> None:
    text = (REPO_ROOT / "backend/app/services/production_stage_service.py").read_text(encoding="utf-8")
    body = _function_body(text, "_append_history")

    assert "db.production_stage_instances.update_one(" in body
    assert '"tenant_id": tenant_id' in body
    assert '"id": stage_id' in body

    calls = _call_texts(text, "await _append_history")
    assert calls
    for call in calls:
        assert "tenant_id=tenant_id" in call
        assert "stage_id=stage_id" in call
        assert "entry=" in call
    assert "_append_history(stage_id," not in text


def test_wrap_inspection_public_token_filters_keep_tenant_and_parent_scope() -> None:
    text = (REPO_ROOT / "backend/app/services/wrap_lab.py").read_text(encoding="utf-8")
    helper = _function_body(text, "_inspection_review_token_filter")

    for expected in [
        '"tenant_id": token["tenant_id"]',
        '"id": token["id"]',
        '"action": "wrap_inspection_review"',
        '"parent_type": "wrap_inspection"',
        '"parent_id": token["parent_id"]',
    ]:
        assert expected in helper

    create_body = _function_body(text, "create_inspection_review_link")
    assert "_inspection_review_token_filter(token_doc)" in create_body

    staff_update_body = _function_body(text, "update_inspection_review_link")
    assert "_inspection_review_token_filter(token)" in staff_update_body

    resolver_body = _function_body(text, "_resolve_public_inspection_review_token")
    assert '"token_hash": hash_token(raw_token)' in resolver_body
    assert '"action": "wrap_inspection_review"' in resolver_body
    assert '"parent_type": "wrap_inspection"' in resolver_body
    assert '"parent_id": inspection_id' in resolver_body
    assert "_inspection_review_token_filter(token)" in resolver_body

    view_body = _function_body(text, "public_view_inspection_review")
    assert "_inspection_review_token_filter(token)" in view_body

    sign_body = _function_body(text, "public_sign_inspection_review")
    assert sign_body.count("_inspection_review_token_filter(token)") >= 2

    assert 'public_action_tokens.update_one({"id": token["id"]}' not in text
    assert 'public_action_tokens.find_one({"id": token["id"]}' not in text

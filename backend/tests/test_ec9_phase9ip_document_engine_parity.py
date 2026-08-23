"""EC9 Phase 9I-P pure document-engine extraction tests."""
from __future__ import annotations

from copy import deepcopy
import ast
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server import app
from app.core.db import db
from app.deps import get_current_user
from app.services.commerce_totals import (
    compute_document_totals,
    compute_line_totals,
    compute_pricing_summary,
)
from app.services.order_pricing import compute_document_totals_with_pricing_adjustments
from pricing_engine import document_engine
from pricing_engine.document_engine import calculate_document
from pricing_engine.validation import ContractValidationError


PROHIBITED_IMPORT_ROOTS = {
    "app",
    "fastapi",
    "motor",
    "pymongo",
    "requests",
    "httpx",
    "stripe",
    "openai",
}

REPO_ROOT = Path(__file__).resolve().parents[2]
EMBEDDED_ENGINE_DIR = REPO_ROOT / "backend" / "pricing_engine"


def _override_as(user: dict):
    async def _dep():
        return user

    return _dep


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override_as(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _snapshot(*, order_minimum: float | None = 40.0, item_minimum_total: float | None = 20.0) -> dict:
    snapshot = {
        "minimum_policy": "digital_print_item_minimum_document_order_minimum",
        "minimum_scope": "digital_print_line_item",
    }
    if order_minimum is not None:
        snapshot["order_minimum"] = order_minimum
    if item_minimum_total is not None:
        snapshot["item_minimum_total"] = item_minimum_total
    return snapshot


def _line(
    line_id: str,
    *,
    category: str = "digital_print",
    subtotal: int = 2000,
    discount: int = 0,
    tax: int = 0,
    total: int | None = None,
    order_minimum: float | None = 40.0,
    snapshot: dict | None = None,
) -> dict:
    return {
        "id": line_id,
        "category": category,
        "quantity": 1,
        "unit_price_cents": subtotal,
        "line_subtotal_cents": subtotal,
        "discount_cents": discount,
        "tax_cents": tax,
        "line_total_cents": subtotal - discount + tax if total is None else total,
        "selected_price_source": "suggested" if category == "digital_print" else "manual",
        "pricing_status": "calculated" if category == "digital_print" else "manual",
        "pricing_snapshot": snapshot if snapshot is not None else _snapshot(order_minimum=order_minimum),
    }


def _assert_minimum(totals: dict, *, eligible: int, order_minimum: int, adjustment: int, subtotal: int, total: int) -> None:
    evidence = totals["digital_print_minimum"]
    assert evidence["policy"] == "digital_print_document_order_minimum"
    assert evidence["scope"] == "quote_or_order_document"
    assert evidence["category"] == "digital_print"
    assert evidence["eligible_subtotal_cents"] == eligible
    assert evidence["order_minimum_cents"] == order_minimum
    assert evidence["order_minimum_adjustment_cents"] == adjustment
    assert evidence["adjustment_applied"] is (adjustment > 0)
    assert evidence["adjustment_count"] == (1 if adjustment > 0 else 0)
    assert totals["subtotal_cents"] == subtotal
    assert totals["total_cents"] == total
    assert totals["document_pricing_adjustment_cents"] == adjustment
    assert totals["digital_print_order_minimum_adjustment_cents"] == adjustment


async def _seed_customer(tenant_id: str) -> str:
    customer_id = f"cust-{uuid.uuid4().hex[:8]}"
    await db.customers.insert_one({
        "id": customer_id,
        "tenant_id": tenant_id,
        "name": "Phase 9I-P Buyer",
        "email": "phase9ip@example.com",
    })
    return customer_id


async def _new_quote(client: AsyncClient, customer_id: str) -> str:
    response = await client.post("/api/quotes", json={"customer_id": customer_id, "job_name": "9I-P quote"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _new_order(client: AsyncClient, customer_id: str) -> str:
    response = await client.post("/api/orders", json={"customer_id": customer_id, "job_name": "9I-P order"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _digital_payload(**overrides) -> dict:
    payload = {
        "description": "Tiny digital print",
        "quantity": 1,
        "unit_price_cents": 1,
        "category": "digital_print",
        "width_inches": 6,
        "height_inches": 6,
        "selected_price_source": "suggested",
    }
    payload.update(overrides)
    return payload


def test_pure_document_engine_imports_without_saas_startup():
    code = (
        "import sys; "
        "from pricing_engine.document_engine import calculate_document; "
        "blocked=[m for m in sys.modules if m == 'app' or m.startswith('app.')]; "
        "assert blocked == [], blocked; "
        "print(calculate_document.__name__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd="backend",
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == "calculate_document"


def test_pure_document_engine_has_no_saas_database_auth_or_network_imports():
    package_root = Path(document_engine.__file__).resolve().parent
    assert not EMBEDDED_ENGINE_DIR.exists()
    assert not package_root.is_relative_to(EMBEDDED_ENGINE_DIR)
    assert "site-packages" in package_root.parts or "dist-packages" in package_root.parts
    roots = sorted(package_root.glob("*.py"))
    findings: list[tuple[str, int, str]] = []
    for path in roots:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in PROHIBITED_IMPORT_ROOTS:
                        findings.append((str(path), node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                root = module.split(".")[0]
                if root in PROHIBITED_IMPORT_ROOTS:
                    findings.append((str(path), node.lineno, module))
    assert findings == []


def test_empty_single_multiple_discount_tax_and_negative_line_totals_match_current_contract():
    assert calculate_document([]) == {
        "subtotal_cents": 0,
        "discount_cents": 0,
        "tax_cents": 0,
        "total_cents": 0,
        "item_count": 0,
        "line_subtotal_cents": 0,
        "line_total_cents": 0,
        "document_pricing_adjustment_cents": 0,
        "digital_print_order_minimum_adjustment_cents": 0,
        "digital_print_minimum": {
            "policy": "digital_print_document_order_minimum",
            "scope": "quote_or_order_document",
            "category": "digital_print",
            "eligible_line_items": [],
            "eligible_line_item_ids": [],
            "eligible_subtotal_cents": 0,
            "order_minimum_cents": 0,
            "order_minimum_adjustment_cents": 0,
            "adjustment_applied": False,
            "adjustment_count": 0,
            "document_subtotal_before_adjustment_cents": 0,
            "document_subtotal_after_adjustment_cents": 0,
            "document_total_after_adjustment_cents": 0,
        },
    }

    single = calculate_document([_line("manual", category="custom", subtotal=1250, discount=50, tax=100, snapshot={})])
    assert single["line_subtotal_cents"] == 1250
    assert single["discount_cents"] == 50
    assert single["tax_cents"] == 100
    assert single["line_total_cents"] == 1300
    assert single["total_cents"] == 1300

    multiple = calculate_document([
        _line("one", category="custom", subtotal=1000, total=0, snapshot={}),
        _line("two", category="services", subtotal=500, discount=25, tax=15, snapshot={}),
    ])
    assert multiple["line_subtotal_cents"] == 1500
    assert multiple["discount_cents"] == 25
    assert multiple["tax_cents"] == 15
    assert multiple["line_total_cents"] == 490
    assert multiple["item_count"] == 2
    assert compute_line_totals(quantity=1, unit_price_cents=100, discount_cents=999_999)["line_total_cents"] == 0


@pytest.mark.parametrize(
    "subtotal,order_minimum,expected_adjustment",
    [
        (2000, 40.0, 2000),
        (4000, 40.0, 0),
        (5500, 40.0, 0),
    ],
)
def test_digital_print_document_minimum_below_at_and_above(subtotal, order_minimum, expected_adjustment):
    totals = calculate_document([_line("dp", subtotal=subtotal, order_minimum=order_minimum)])

    _assert_minimum(
        totals,
        eligible=subtotal,
        order_minimum=int(order_minimum * 100),
        adjustment=expected_adjustment,
        subtotal=subtotal + expected_adjustment,
        total=subtotal + expected_adjustment,
    )


def test_multiple_digital_print_lines_share_one_minimum_and_mixed_categories_are_excluded():
    totals = calculate_document([
        _line("dp-1", subtotal=1000),
        _line("banner", category="banners", subtotal=9999, snapshot={}),
        _line("dp-2", subtotal=1500),
    ])

    _assert_minimum(totals, eligible=2500, order_minimum=4000, adjustment=1500, subtotal=13999, total=13999)
    assert totals["digital_print_minimum"]["eligible_line_item_ids"] == ["dp-1", "dp-2"]
    assert totals["digital_print_minimum"]["adjustment_count"] == 1


def test_document_minimum_order_of_operations_preserves_protected_discount_tax_example():
    totals = calculate_document([_line("dp", subtotal=2000, discount=500, tax=300)])

    _assert_minimum(totals, eligible=2000, order_minimum=4000, adjustment=2000, subtotal=4000, total=3800)
    assert totals["discount_cents"] == 500
    assert totals["tax_cents"] == 300
    assert totals["line_total_cents"] == 1800


def test_frozen_minimum_evidence_controls_totals_and_legacy_missing_evidence_does_not_invent_adjustment():
    old_snapshot = _snapshot(order_minimum=40.0)
    changed_settings_snapshot = _snapshot(order_minimum=125.0)

    old_totals = calculate_document([_line("old", subtotal=2000, snapshot=old_snapshot)])
    changed_totals = calculate_document([_line("changed", subtotal=2000, snapshot=changed_settings_snapshot)])
    legacy_totals = calculate_document([_line("legacy", subtotal=2000, snapshot={})])

    _assert_minimum(old_totals, eligible=2000, order_minimum=4000, adjustment=2000, subtotal=4000, total=4000)
    _assert_minimum(changed_totals, eligible=2000, order_minimum=12500, adjustment=10500, subtotal=12500, total=12500)
    _assert_minimum(legacy_totals, eligible=2000, order_minimum=0, adjustment=0, subtotal=2000, total=2000)
    assert old_snapshot == _snapshot(order_minimum=40.0)


def test_pricing_summary_and_compatibility_wrappers_delegate_to_pure_engine():
    items = [
        {
            "quantity": 2,
            "line_subtotal_cents": 4000,
            "line_total_cents": 3800,
            "discount_cents": 300,
            "tax_cents": 100,
            "suggested_price_cents": 2000,
            "estimated_cost_cents": 1200,
            "estimated_profit_cents": 2600,
            "selected_price_source": "suggested",
            "calculation_warnings": ["warn"],
        },
        {
            "quantity": 1,
            "line_subtotal_cents": 500,
            "line_total_cents": 500,
            "selected_price_source": "manual",
        },
    ]

    assert compute_document_totals(items) == document_engine.compute_document_totals(items)
    assert compute_document_totals_with_pricing_adjustments(items) == calculate_document(items)
    summary = compute_pricing_summary(items)
    assert summary["total_estimated_cost_cents"] == 1200
    assert summary["total_suggested_price_amount_cents"] == 4000
    assert summary["total_manual_price_amount_cents"] == 500
    assert summary["selected_final_total_cents"] == 4300
    assert summary["items_with_warnings_count"] == 1


def test_client_supplied_or_boolean_authoritative_money_is_rejected_or_ignored():
    with pytest.raises(ContractValidationError):
        calculate_document([_line("bad", subtotal=True)])

    forged = _line("dp", subtotal=2000)
    forged["digital_print_minimum"] = {"order_minimum_adjustment_cents": 999999}
    forged["document_pricing_adjustment_cents"] = 999999
    totals = calculate_document([forged])

    _assert_minimum(totals, eligible=2000, order_minimum=4000, adjustment=2000, subtotal=4000, total=4000)


@pytest.mark.asyncio
async def test_quote_and_order_lifecycle_paths_use_pure_document_engine(monkeypatch, seeded_users):
    original = document_engine.calculate_document
    calls: list[list[dict]] = []

    def spy(items):
        item_list = list(items or [])
        calls.append(deepcopy(item_list))
        return original(item_list)

    monkeypatch.setattr(document_engine, "calculate_document", spy)
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        order_id = await _new_order(client, customer_id)
        quote_line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        order_line = await client.post(f"/api/orders/{order_id}/items", json=_digital_payload())
        assert quote_line.status_code == 201, quote_line.text
        assert order_line.status_code == 201, order_line.text

        quote = await client.get(f"/api/quotes/{quote_id}")
        order = await client.get(f"/api/orders/{order_id}")
        assert quote.status_code == 200, quote.text
        assert order.status_code == 200, order.text
        _assert_minimum(quote.json()["totals"], eligible=2000, order_minimum=4000, adjustment=2000, subtotal=4000, total=4000)
        _assert_minimum(order.json()["totals"], eligible=2000, order_minimum=4000, adjustment=2000, subtotal=4000, total=4000)

        patched = await client.patch(
            f"/api/orders/{order_id}/items/{order_line.json()['id']}",
            json={"width_inches": 24, "height_inches": 24, "recalculate": True},
        )
        assert patched.status_code == 200, patched.text
        deleted = await client.delete(f"/api/orders/{order_id}/items/{order_line.json()['id']}")
        assert deleted.status_code == 204, deleted.text

    assert calls
    assert any(any(item.get("category") == "digital_print" for item in call) for call in calls)
    _clear_auth()


@pytest.mark.asyncio
async def test_quote_revision_and_conversion_preserve_frozen_document_evidence_without_recalculation(seeded_users):
    user = seeded_users["user_a"]
    customer_id = await _seed_customer(user["tenant_id"])
    async with await _client_as(user) as client:
        quote_id = await _new_quote(client, customer_id)
        line = await client.post(f"/api/quotes/{quote_id}/line-items", json=_digital_payload())
        assert line.status_code == 201, line.text
        sent = await client.post(f"/api/quotes/{quote_id}/status", json={"status": "sent"})
        assert sent.status_code == 200, sent.text
        patched = await client.patch(
            f"/api/quotes/{quote_id}/line-items/{line.json()['id']}",
            json={"width_inches": 48, "height_inches": 96, "recalculate": True},
        )
        assert patched.status_code == 200, patched.text
        revision = await client.get(f"/api/quotes/{quote_id}/revisions/1")
        assert revision.status_code == 200, revision.text
        _assert_minimum(revision.json(), eligible=2000, order_minimum=4000, adjustment=2000, subtotal=4000, total=4000)

        second_quote_id = await _new_quote(client, customer_id)
        second_line = await client.post(f"/api/quotes/{second_quote_id}/line-items", json=_digital_payload())
        assert second_line.status_code == 201, second_line.text
        await client.patch(
            "/api/pricing/settings/categories/digital_print",
            json={"extras": {"item_minimum": 55.0, "order_minimum": 125.0}},
        )
        converted = await client.post(f"/api/quotes/{second_quote_id}/convert-to-order", json={})
        assert converted.status_code == 200, converted.text
        _assert_minimum(converted.json()["order"], eligible=2000, order_minimum=4000, adjustment=2000, subtotal=4000, total=4000)
        stored_line = await db.quote_line_items.find_one({"id": second_line.json()["id"], "tenant_id": user["tenant_id"]}, {"_id": 0})
        assert stored_line["pricing_snapshot"]["order_minimum"] == 40.0
    _clear_auth()

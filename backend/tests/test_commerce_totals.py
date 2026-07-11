"""EC3 — Commerce totals unit tests."""
from app.services.commerce_totals import compute_document_totals, compute_line_totals


def test_line_totals_basic():
    t = compute_line_totals(quantity=3, unit_price_cents=1000)
    assert t["line_subtotal_cents"] == 3000
    assert t["line_total_cents"] == 3000


def test_line_totals_discount_tax():
    t = compute_line_totals(quantity=2, unit_price_cents=500, discount_cents=100, tax_cents=80)
    assert t["line_subtotal_cents"] == 1000
    assert t["discount_cents"] == 100
    assert t["tax_cents"] == 80
    assert t["line_total_cents"] == 980


def test_line_totals_never_negative():
    t = compute_line_totals(quantity=1, unit_price_cents=100, discount_cents=999_999)
    assert t["line_total_cents"] == 0


def test_document_totals_sums_line_items():
    items = [
        {"line_subtotal_cents": 1000, "discount_cents": 100, "tax_cents": 0, "line_total_cents": 900},
        {"line_subtotal_cents": 500, "discount_cents": 0, "tax_cents": 40, "line_total_cents": 540},
    ]
    totals = compute_document_totals(items)
    assert totals["subtotal_cents"] == 1500
    assert totals["discount_cents"] == 100
    assert totals["tax_cents"] == 40
    assert totals["total_cents"] == 1440
    assert totals["item_count"] == 2


def test_line_totals_rejects_invalid_inputs_gracefully():
    t = compute_line_totals(quantity=-5, unit_price_cents=-100)
    assert t["line_subtotal_cents"] == 0
    assert t["line_total_cents"] == 0

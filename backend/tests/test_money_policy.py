"""EC1 — Money Policy Tests.

Verifies:
  1. Commerce fields on Quote/Order/OrderItem/WorkOrderItemSnapshot/Invoice/
     InvoiceLineItem/Payment carry the `_cents` suffix.
  2. Conversion helpers produce integer cents with proper half-up rounding.
  3. Pricing configuration (starter_defaults.SHOP_DEFAULTS et al) remains
     dollar-based.
"""
from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from app.core.money import cents_to_dollars, dollars_to_cents, sum_cents
from app.models import invoice as invoice_models
from app.models import order as order_models
from app.models import quote as quote_models
from app.models import work_order as wo_models


def _money_field_names(pydantic_cls) -> list[str]:
    names: list[str] = []
    for name, field in pydantic_cls.model_fields.items():
        ann = field.annotation
        ann_str = str(ann)
        if any(k in ann_str for k in ["int", "Decimal", "float"]):
            # Heuristic: names ending in a common money suffix without _cents
            for suffix in ("total", "unit_price", "line_total", "amount", "balance", "paid"):
                if suffix in name:
                    names.append(name)
                    break
    return names


def _classes_in_module(module):
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ == module.__name__:
            yield name, obj


def test_commerce_money_fields_use_cents_suffix():
    modules = [quote_models, order_models, invoice_models, wo_models]
    offenders: list[str] = []
    for mod in modules:
        for cls_name, cls in _classes_in_module(mod):
            if not hasattr(cls, "model_fields"):
                continue
            for field_name in _money_field_names(cls):
                if not field_name.endswith("_cents"):
                    offenders.append(f"{mod.__name__}.{cls_name}.{field_name}")
    assert offenders == [], (
        "Ambiguous commerce money fields detected (missing _cents suffix): "
        f"{offenders}"
    )


@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, 0),
        (1, 100),
        (1.00, 100),
        ("1.00", 100),
        (Decimal("1.00"), 100),
        (12.34, 1234),
        ("12.345", 1235),  # half-up
        (0.005, 1),  # half-up
        (-0.01, -1),
    ],
)
def test_dollars_to_cents(amount, expected):
    assert dollars_to_cents(amount) == expected


def test_dollars_to_cents_rejects_bad_types():
    with pytest.raises(TypeError):
        dollars_to_cents(True)
    with pytest.raises(TypeError):
        dollars_to_cents(None)
    with pytest.raises(Exception):  # noqa: B017 — either Value or Decimal error
        dollars_to_cents("not-a-number")


def test_cents_to_dollars_roundtrip():
    for cents in [0, 1, 100, 1234, 999999]:
        assert dollars_to_cents(cents_to_dollars(cents)) == cents


def test_sum_cents_refuses_non_int():
    assert sum_cents([100, 200, 300]) == 600
    with pytest.raises(TypeError):
        sum_cents([100, 1.5])
    with pytest.raises(TypeError):
        sum_cents([100, True])


def test_pricing_config_remains_dollar_based():
    """Guard: SHOP_DEFAULTS et al are dollar-based; we don't accidentally cast
    them to cents anywhere at import."""
    from app.services import starter_defaults

    sd = starter_defaults.SHOP_DEFAULTS
    # Shop rate is a small positive dollar number; if someone converted to
    # cents it would be >= 100x its current value.
    assert isinstance(sd, dict)
    if "shop_rate_per_hour" in sd:
        assert sd["shop_rate_per_hour"] < 500, (
            "SHOP_DEFAULTS.shop_rate_per_hour looks like cents; must remain dollars"
        )

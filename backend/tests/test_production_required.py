"""EC3 — production_required rule tests."""
from app.services.order_item_rules import (
    NON_PRODUCTION_CATEGORIES,
    PHYSICAL_PRODUCTION_CATEGORIES,
    default_production_required,
)


def test_physical_production_categories_default_true():
    for cat in PHYSICAL_PRODUCTION_CATEGORIES:
        assert default_production_required(cat) is True, f"{cat} should require production"


def test_non_production_categories_default_false():
    for cat in NON_PRODUCTION_CATEGORIES:
        assert default_production_required(cat) is False, f"{cat} should NOT require production"


def test_unknown_category_defaults_true():
    assert default_production_required("random_junk") is True
    assert default_production_required(None) is True


def test_categories_are_disjoint():
    assert PHYSICAL_PRODUCTION_CATEGORIES & NON_PRODUCTION_CATEGORIES == set()

"""EC7 phase 7b — Deterministic full-capability test supplier adapter.

Owner-approved (Option A): use this adapter — not a live vendor — as the
first EC7 supplier connector. It exercises every capability of the connector
interface so downstream services (shortage calc, purchasing recommendation,
Supply Center, receiving) have a stable substrate for tests and demos.

**All data is CLEARLY SYNTHETIC.** Vendor names are believable but do NOT
copy SanMar / Grimco / Fellers / AlphaBroder / Uline pricing or SKUs.

Catalog size (target 60–100 SKUs, delivered ~80):
    ~35 apparel (styles × colors × sizes)
    ~22 vinyl / laminate / application tape
    ~12 substrates
    ~11 hardware / shop supplies

Purchasing conditions demonstrated:
    - Multiple warehouses per vendor
    - Different available quantities (including 0 / discontinued)
    - Partial fulfillment (a warehouse only has some of the requested qty)
    - Account-specific pricing
    - Quantity breaks (bulk pricing)
    - Package quantities
    - Minimum order requirements
    - Shipping + freight + handling fees
    - Warehouse splits (multiple ships in one PO)
    - Preferred-vendor flag
    - Discontinued products
    - Lead-time differences
    - Higher unit price but lower delivered cost
    - Cheaper option with slower arrival
    - Incompatible products that must NOT be recommended as substitutes
      (cast vs calendared vinyl / different adhesive systems)

Seed generation is:
    - repeatable (fixed IDs derived from tenant_id + supplier_sku)
    - idempotent (upsert-based)
    - isolated to development and test environments
    - disabled in production (guarded by ENV != production)
    - easy to reset
    - clearly labeled as synthetic demo data
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from ...core.db import db
from ...core.time_utils import utc_now, prepare_for_mongo, serialize_doc
from .base import SupplierConnectorBase, ConnectorCapability, RATE_ESTIMATED


# ---------------------------------------------------------------------------
# Deterministic ID helper — same inputs always produce the same UUID-like id.
# ---------------------------------------------------------------------------
def _det_id(prefix: str, *parts: str) -> str:
    h = hashlib.sha1("|".join([prefix, *parts]).encode("utf-8")).hexdigest()
    return f"{prefix}-{h[:20]}"


# ---------------------------------------------------------------------------
# Synthetic vendor definitions
# ---------------------------------------------------------------------------
SYNTHETIC_VENDORS: list[dict[str, Any]] = [
    {
        "key": "northwind_signworks",
        "name": "Northwind Signworks Supply",
        "connector_key": "test_adapter",
        "tier": "test_adapter",
        "categories": ["vinyl", "laminate", "application_tape", "substrate", "banner", "hardware", "supplies"],
        "preferred": True,
        "warehouses": [
            {"code": "NW-PDX", "name": "Northwind Portland", "region": "west", "city": "Portland", "state": "OR",
             "base_ship_cost_cents": 1500, "per_item_ship_cost_cents": 250, "handling_fee_cents": 300,
             "freight_multiplier": 1.0},
            {"code": "NW-KCK", "name": "Northwind Kansas City", "region": "central", "city": "Kansas City", "state": "MO",
             "base_ship_cost_cents": 2200, "per_item_ship_cost_cents": 350, "handling_fee_cents": 300,
             "freight_multiplier": 1.0},
            {"code": "NW-CLT", "name": "Northwind Charlotte", "region": "east", "city": "Charlotte", "state": "NC",
             "base_ship_cost_cents": 2600, "per_item_ship_cost_cents": 400, "handling_fee_cents": 400,
             "freight_multiplier": 1.0},
        ],
    },
    {
        "key": "cascadia_wrap",
        "name": "Cascadia Wrap Distributors",
        "connector_key": "test_adapter",
        "tier": "test_adapter",
        "categories": ["vinyl", "laminate", "application_tape", "printable_media"],
        "preferred": False,
        "warehouses": [
            {"code": "CW-SEA", "name": "Cascadia Seattle", "region": "west", "city": "Seattle", "state": "WA",
             "base_ship_cost_cents": 900, "per_item_ship_cost_cents": 200, "handling_fee_cents": 200,
             "freight_multiplier": 1.0},
            {"code": "CW-DEN", "name": "Cascadia Denver", "region": "central", "city": "Denver", "state": "CO",
             "base_ship_cost_cents": 1800, "per_item_ship_cost_cents": 300, "handling_fee_cents": 300,
             "freight_multiplier": 1.0},
        ],
    },
    {
        "key": "meridian_apparel",
        "name": "Meridian Apparel Blanks",
        "connector_key": "test_adapter",
        "tier": "test_adapter",
        "categories": ["apparel"],
        "preferred": False,
        "warehouses": [
            {"code": "MA-DAL", "name": "Meridian Dallas", "region": "south", "city": "Dallas", "state": "TX",
             "base_ship_cost_cents": 1600, "per_item_ship_cost_cents": 90, "handling_fee_cents": 200,
             "freight_multiplier": 1.0},
            {"code": "MA-ATL", "name": "Meridian Atlanta", "region": "southeast", "city": "Atlanta", "state": "GA",
             "base_ship_cost_cents": 1900, "per_item_ship_cost_cents": 110, "handling_fee_cents": 200,
             "freight_multiplier": 1.0},
        ],
    },
    {
        "key": "redwood_hardware",
        "name": "Redwood Hardware & Shop Supply",
        "connector_key": "test_adapter",
        "tier": "test_adapter",
        "categories": ["hardware", "supplies", "packaging"],
        "preferred": False,
        "warehouses": [
            {"code": "RH-RNO", "name": "Redwood Reno", "region": "west", "city": "Reno", "state": "NV",
             "base_ship_cost_cents": 1400, "per_item_ship_cost_cents": 150, "handling_fee_cents": 100,
             "freight_multiplier": 1.0},
        ],
    },
]


# ---------------------------------------------------------------------------
# Catalog: category -> list of (supplier_sku, description, variants, pricing, ...)
# Each entry compiles into 1-N SupplierProduct rows via _expand_variants().
# Stock levels are seeded per warehouse to demonstrate all conditions listed
# in the module docstring.
# ---------------------------------------------------------------------------

# Apparel — 8 base styles expanding to 35 SKUs (style × color × size).
APPAREL_STYLES: list[dict[str, Any]] = [
    {
        "vendor": "meridian_apparel", "family": "MER-TEE-CLA", "brand": "Meridian",
        "series": "Classic Crew Tee", "compatible_group": None,
        "list_cents": 795, "account_cents": 545, "package_qty": 6, "moq": 12,
        "colors": ["Black", "White", "Navy"], "sizes": ["S", "M", "L"],
        "breaks": [{"min_qty": 24, "unit_price_cents": 495}, {"min_qty": 72, "unit_price_cents": 465}],
        "stock": {"MA-DAL": [80, 60, 40, 65, 60, 55, 70, 50, 45],
                  "MA-ATL": [50, 30, 40, 20, 25, 30, 35, 20, 15]},
        "lead": {"MA-DAL": 2, "MA-ATL": 3},
    },
    {
        "vendor": "meridian_apparel", "family": "MER-HDY-PUL", "brand": "Meridian",
        "series": "Pullover Hoodie 10oz", "compatible_group": None,
        "list_cents": 2495, "account_cents": 1795, "package_qty": 4, "moq": 8,
        "colors": ["Black", "Charcoal", "Sport Gray"], "sizes": ["M", "L", "XL"],
        "breaks": [{"min_qty": 24, "unit_price_cents": 1595}],
        "stock": {"MA-DAL": [30, 25, 20, 15, 10, 20, 15, 10, 5],
                  "MA-ATL": [10, 15, 0, 8, 5, 6, 4, 3, 0]},
        "lead": {"MA-DAL": 3, "MA-ATL": 4},
    },
    {
        "vendor": "meridian_apparel", "family": "MER-PLO-COT", "brand": "Meridian",
        "series": "Cotton Polo", "compatible_group": None,
        "list_cents": 1495, "account_cents": 1095, "package_qty": 3, "moq": 6,
        "colors": ["Black", "Navy", "White"], "sizes": ["M", "L"],
        "breaks": [{"min_qty": 24, "unit_price_cents": 995}],
        "stock": {"MA-DAL": [20, 18, 15, 12, 10, 14],
                  "MA-ATL": [8, 6, 0, 4, 2, 0]},
        "lead": {"MA-DAL": 2, "MA-ATL": 3},
    },
    {
        "vendor": "meridian_apparel", "family": "MER-CAP-STR", "brand": "Meridian",
        "series": "Structured Snapback Cap", "compatible_group": None,
        "list_cents": 995, "account_cents": 695, "package_qty": 6, "moq": 12,
        "colors": ["Black", "Navy", "Red"], "sizes": ["OSFA"],
        "breaks": [{"min_qty": 48, "unit_price_cents": 595}],
        "stock": {"MA-DAL": [90, 60, 40], "MA-ATL": [30, 20, 15]},
        "lead": {"MA-DAL": 2, "MA-ATL": 3},
    },
    {
        "vendor": "meridian_apparel", "family": "MER-BAG-TOTE", "brand": "Meridian",
        "series": "Canvas Tote 12oz", "compatible_group": None,
        "list_cents": 895, "account_cents": 645, "package_qty": 6, "moq": 12,
        "colors": ["Natural", "Black"], "sizes": ["OSFA"],
        "breaks": [{"min_qty": 48, "unit_price_cents": 545}],
        "stock": {"MA-DAL": [40, 30], "MA-ATL": [15, 10]},
        "lead": {"MA-DAL": 2, "MA-ATL": 3},
    },
    {
        "vendor": "meridian_apparel", "family": "MER-TEE-PRE", "brand": "Meridian",
        "series": "Premium Ringspun Tee", "compatible_group": None,
        "list_cents": 1095, "account_cents": 795, "package_qty": 6, "moq": 12,
        "colors": ["Black", "White", "Heather Gray"], "sizes": ["M", "L"],
        "breaks": [{"min_qty": 24, "unit_price_cents": 695}, {"min_qty": 72, "unit_price_cents": 645}],
        "stock": {"MA-DAL": [50, 40, 35, 45, 30, 25],
                  "MA-ATL": [20, 25, 15, 10, 12, 8]},
        "lead": {"MA-DAL": 2, "MA-ATL": 3},
    },
]

# Vinyl / laminate / application tape — 22 SKUs.
VINYL_ROWS: list[dict[str, Any]] = [
    # Cast wrap vinyl (compatible_group = cast_wrap)
    {"vendor": "northwind_signworks", "sku": "NW-CST-WHT", "family": "Vinyl", "brand": "SignFlex",
     "series": "PermaCast Wrap", "desc": "PermaCast Wrap Vinyl 60\" Gloss White",
     "category": "vinyl", "compatible_group": "cast_wrap",
     "variant": {"color": "White", "finish": "Gloss", "width_inches": 60, "length_feet": 25, "type": "cast"},
     "list_cents": 22500, "account_cents": 18900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 17500}],
     "stock": {"NW-PDX": (12, 3), "NW-KCK": (5, 5), "NW-CLT": (2, 7)},
     "purchase_unit": "roll", "freight_class": "ltl", "incompatible_with": []},
    {"vendor": "northwind_signworks", "sku": "NW-CST-BLK", "family": "Vinyl", "brand": "SignFlex",
     "series": "PermaCast Wrap", "desc": "PermaCast Wrap Vinyl 60\" Gloss Black",
     "category": "vinyl", "compatible_group": "cast_wrap",
     "variant": {"color": "Black", "finish": "Gloss", "width_inches": 60, "length_feet": 25, "type": "cast"},
     "list_cents": 22500, "account_cents": 18900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 17500}],
     "stock": {"NW-PDX": (8, 3), "NW-KCK": (10, 5), "NW-CLT": (6, 7)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-CST-RED", "family": "Vinyl", "brand": "SignFlex",
     "series": "PermaCast Wrap", "desc": "PermaCast Wrap Vinyl 60\" Matte Red",
     "category": "vinyl", "compatible_group": "cast_wrap",
     "variant": {"color": "Red", "finish": "Matte", "width_inches": 60, "length_feet": 25, "type": "cast"},
     "list_cents": 24500, "account_cents": 20900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (4, 3), "NW-KCK": (0, 5), "NW-CLT": (3, 7)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "cascadia_wrap", "sku": "CW-CST-WHT", "family": "Vinyl", "brand": "AeroWrap",
     "series": "AirRelease Cast", "desc": "AirRelease Cast Wrap 60\" Gloss White",
     "category": "vinyl", "compatible_group": "cast_wrap",
     "variant": {"color": "White", "finish": "Gloss", "width_inches": 60, "length_feet": 25, "type": "cast"},
     "list_cents": 21500, "account_cents": 17900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 16900}],
     "stock": {"CW-SEA": (15, 2), "CW-DEN": (8, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "cascadia_wrap", "sku": "CW-CST-BLK", "family": "Vinyl", "brand": "AeroWrap",
     "series": "AirRelease Cast", "desc": "AirRelease Cast Wrap 60\" Gloss Black",
     "category": "vinyl", "compatible_group": "cast_wrap",
     "variant": {"color": "Black", "finish": "Gloss", "width_inches": 60, "length_feet": 25, "type": "cast"},
     "list_cents": 21500, "account_cents": 17900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 16900}],
     "stock": {"CW-SEA": (10, 2), "CW-DEN": (6, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "cascadia_wrap", "sku": "CW-CST-BLU", "family": "Vinyl", "brand": "AeroWrap",
     "series": "AirRelease Cast", "desc": "AirRelease Cast Wrap 60\" Metallic Blue",
     "category": "vinyl", "compatible_group": "cast_wrap",
     "variant": {"color": "Metallic Blue", "finish": "Metallic", "width_inches": 60, "length_feet": 25, "type": "cast"},
     "list_cents": 26900, "account_cents": 22500, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"CW-SEA": (5, 2), "CW-DEN": (2, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    # Calendared cut vinyl (compatible_group = calendared_cut) — NOT interchangeable with cast_wrap.
    {"vendor": "northwind_signworks", "sku": "NW-CAL-WHT", "family": "Vinyl", "brand": "SignFlex",
     "series": "EconCal Cut", "desc": "EconCal Calendared Cut Vinyl 24\" White",
     "category": "vinyl", "compatible_group": "calendared_cut",
     "variant": {"color": "White", "finish": "Gloss", "width_inches": 24, "length_feet": 50, "type": "calendared"},
     "list_cents": 5500, "account_cents": 3900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 6, "unit_price_cents": 3500}],
     "stock": {"NW-PDX": (24, 2), "NW-KCK": (12, 4), "NW-CLT": (8, 5)},
     "purchase_unit": "roll"},
    {"vendor": "northwind_signworks", "sku": "NW-CAL-BLK", "family": "Vinyl", "brand": "SignFlex",
     "series": "EconCal Cut", "desc": "EconCal Calendared Cut Vinyl 24\" Black",
     "category": "vinyl", "compatible_group": "calendared_cut",
     "variant": {"color": "Black", "finish": "Gloss", "width_inches": 24, "length_feet": 50, "type": "calendared"},
     "list_cents": 5500, "account_cents": 3900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 6, "unit_price_cents": 3500}],
     "stock": {"NW-PDX": (20, 2), "NW-KCK": (16, 4), "NW-CLT": (10, 5)},
     "purchase_unit": "roll"},
    {"vendor": "northwind_signworks", "sku": "NW-CAL-RED", "family": "Vinyl", "brand": "SignFlex",
     "series": "EconCal Cut", "desc": "EconCal Calendared Cut Vinyl 24\" Red",
     "category": "vinyl", "compatible_group": "calendared_cut",
     "variant": {"color": "Red", "finish": "Gloss", "width_inches": 24, "length_feet": 50, "type": "calendared"},
     "list_cents": 5500, "account_cents": 3900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (14, 2), "NW-KCK": (10, 4), "NW-CLT": (0, 5)},
     "purchase_unit": "roll"},
    {"vendor": "cascadia_wrap", "sku": "CW-CAL-YEL", "family": "Vinyl", "brand": "AeroWrap",
     "series": "CutFlex", "desc": "CutFlex Calendared Cut Vinyl 24\" Yellow",
     "category": "vinyl", "compatible_group": "calendared_cut",
     "variant": {"color": "Yellow", "finish": "Gloss", "width_inches": 24, "length_feet": 50, "type": "calendared"},
     "list_cents": 5300, "account_cents": 3700, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"CW-SEA": (18, 2), "CW-DEN": (12, 4)},
     "purchase_unit": "roll"},
    {"vendor": "cascadia_wrap", "sku": "CW-CAL-GRN", "family": "Vinyl", "brand": "AeroWrap",
     "series": "CutFlex", "desc": "CutFlex Calendared Cut Vinyl 24\" Green",
     "category": "vinyl", "compatible_group": "calendared_cut",
     "variant": {"color": "Green", "finish": "Gloss", "width_inches": 24, "length_feet": 50, "type": "calendared"},
     "list_cents": 5300, "account_cents": 3700, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"CW-SEA": (10, 2), "CW-DEN": (0, 4)},
     "purchase_unit": "roll"},
    # Reflective vinyl (compatible_group = reflective_engineer)
    {"vendor": "northwind_signworks", "sku": "NW-REF-WHT", "family": "Vinyl", "brand": "BrightRoad",
     "series": "Engineer Grade Reflective", "desc": "Engineer Grade Reflective 30\" White",
     "category": "vinyl", "compatible_group": "reflective_engineer",
     "variant": {"color": "White", "finish": "Reflective", "width_inches": 30, "length_feet": 50, "type": "reflective"},
     "list_cents": 12500, "account_cents": 9900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (6, 3), "NW-KCK": (4, 5), "NW-CLT": (0, 7)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-REF-YEL", "family": "Vinyl", "brand": "BrightRoad",
     "series": "Engineer Grade Reflective", "desc": "Engineer Grade Reflective 30\" Yellow",
     "category": "vinyl", "compatible_group": "reflective_engineer",
     "variant": {"color": "Yellow", "finish": "Reflective", "width_inches": 30, "length_feet": 50, "type": "reflective"},
     "list_cents": 12500, "account_cents": 9900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (3, 3), "NW-KCK": (2, 5), "NW-CLT": (2, 7)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-REF-RED", "family": "Vinyl", "brand": "BrightRoad",
     "series": "Engineer Grade Reflective", "desc": "Engineer Grade Reflective 30\" Red (DISCONTINUED)",
     "category": "vinyl", "compatible_group": "reflective_engineer",
     "variant": {"color": "Red", "finish": "Reflective", "width_inches": 30, "length_feet": 50, "type": "reflective"},
     "list_cents": 12500, "account_cents": 9900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (0, 3), "NW-KCK": (0, 5), "NW-CLT": (0, 7)},
     "purchase_unit": "roll", "freight_class": "ltl", "discontinued": True},
    # Print vinyl (blank print media)
    {"vendor": "cascadia_wrap", "sku": "CW-PRT-54", "family": "PrintMedia", "brand": "AeroWrap",
     "series": "PrintReady Solvent Vinyl", "desc": "PrintReady Solvent Vinyl 54\"",
     "category": "printable_media", "compatible_group": "print_vinyl_solvent",
     "variant": {"width_inches": 54, "length_feet": 150, "adhesive": "removable", "type": "solvent_print"},
     "list_cents": 22900, "account_cents": 17900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 16500}],
     "stock": {"CW-SEA": (8, 2), "CW-DEN": (4, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "cascadia_wrap", "sku": "CW-PRT-60", "family": "PrintMedia", "brand": "AeroWrap",
     "series": "PrintReady Solvent Vinyl", "desc": "PrintReady Solvent Vinyl 60\"",
     "category": "printable_media", "compatible_group": "print_vinyl_solvent",
     "variant": {"width_inches": 60, "length_feet": 150, "adhesive": "removable", "type": "solvent_print"},
     "list_cents": 24900, "account_cents": 19500, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 17900}],
     "stock": {"CW-SEA": (6, 2), "CW-DEN": (3, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    # Laminates
    {"vendor": "cascadia_wrap", "sku": "CW-LAM-GLS", "family": "Laminate", "brand": "AeroWrap",
     "series": "ClearGuard Laminate", "desc": "ClearGuard Overlaminate 54\" Gloss",
     "category": "laminate", "compatible_group": "laminate_gloss",
     "variant": {"width_inches": 54, "length_feet": 150, "finish": "Gloss"},
     "list_cents": 19900, "account_cents": 14900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 13500}],
     "stock": {"CW-SEA": (7, 2), "CW-DEN": (5, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "cascadia_wrap", "sku": "CW-LAM-MAT", "family": "Laminate", "brand": "AeroWrap",
     "series": "ClearGuard Laminate", "desc": "ClearGuard Overlaminate 54\" Matte",
     "category": "laminate", "compatible_group": "laminate_matte",
     "variant": {"width_inches": 54, "length_feet": 150, "finish": "Matte"},
     "list_cents": 19900, "account_cents": 14900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 13500}],
     "stock": {"CW-SEA": (5, 2), "CW-DEN": (4, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    {"vendor": "cascadia_wrap", "sku": "CW-LAM-LUS", "family": "Laminate", "brand": "AeroWrap",
     "series": "ClearGuard Laminate", "desc": "ClearGuard Overlaminate 54\" Luster",
     "category": "laminate", "compatible_group": "laminate_luster",
     "variant": {"width_inches": 54, "length_feet": 150, "finish": "Luster"},
     "list_cents": 20500, "account_cents": 15500, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"CW-SEA": (3, 2), "CW-DEN": (0, 4)},
     "purchase_unit": "roll", "freight_class": "ltl"},
    # Application tapes (3 SKUs, incompatible types)
    {"vendor": "northwind_signworks", "sku": "NW-TAP-HT", "family": "AppTape", "brand": "SignFlex",
     "series": "AppMaster Paper", "desc": "AppMaster High-Tack Paper App Tape 24\"",
     "category": "application_tape", "compatible_group": "app_paper_high_tack",
     "variant": {"width_inches": 24, "length_feet": 100, "tack": "high", "material": "paper"},
     "list_cents": 4900, "account_cents": 3500, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (10, 2), "NW-KCK": (8, 3), "NW-CLT": (5, 5)},
     "purchase_unit": "roll"},
    {"vendor": "northwind_signworks", "sku": "NW-TAP-MT", "family": "AppTape", "brand": "SignFlex",
     "series": "AppMaster Clear", "desc": "AppMaster Clear Medium-Tack App Tape 24\"",
     "category": "application_tape", "compatible_group": "app_clear_med_tack",
     "variant": {"width_inches": 24, "length_feet": 100, "tack": "medium", "material": "clear_film"},
     "list_cents": 5900, "account_cents": 4200, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (7, 2), "NW-KCK": (5, 3), "NW-CLT": (0, 5)},
     "purchase_unit": "roll"},
    {"vendor": "northwind_signworks", "sku": "NW-TAP-TR", "family": "AppTape", "brand": "SignFlex",
     "series": "TransferMaster", "desc": "TransferMaster Wet-Apply Transfer Tape 24\"",
     "category": "application_tape", "compatible_group": "app_transfer_wet",
     "variant": {"width_inches": 24, "length_feet": 100, "tack": "low", "material": "paper_wet"},
     "list_cents": 4500, "account_cents": 3300, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (6, 2), "NW-KCK": (4, 3), "NW-CLT": (2, 5)},
     "purchase_unit": "roll"},
]

# Substrates — 12 SKUs.
SUBSTRATE_ROWS: list[dict[str, Any]] = [
    {"vendor": "northwind_signworks", "sku": "NW-ACM-4X8-3", "family": "Substrate", "brand": "SignBoard",
     "series": "AlumaComp", "desc": "AlumaComp ACM Panel 4x8 3mm White",
     "category": "substrate", "compatible_group": "acm_3mm",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_mm": 3, "color": "White"},
     "list_cents": 5500, "account_cents": 3900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 10, "unit_price_cents": 3500}],
     "stock": {"NW-PDX": (40, 3), "NW-KCK": (60, 5), "NW-CLT": (35, 7)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-ACM-4X10-3", "family": "Substrate", "brand": "SignBoard",
     "series": "AlumaComp", "desc": "AlumaComp ACM Panel 4x10 3mm White",
     "category": "substrate", "compatible_group": "acm_3mm",
     "variant": {"width_inches": 48, "height_inches": 120, "thickness_mm": 3, "color": "White"},
     "list_cents": 7500, "account_cents": 5900, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 10, "unit_price_cents": 5300}],
     "stock": {"NW-PDX": (20, 3), "NW-KCK": (25, 5), "NW-CLT": (10, 7)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-ACM-4X8-6", "family": "Substrate", "brand": "SignBoard",
     "series": "AlumaComp", "desc": "AlumaComp ACM Panel 4x8 6mm White",
     "category": "substrate", "compatible_group": "acm_6mm",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_mm": 6, "color": "White"},
     "list_cents": 8500, "account_cents": 6900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (15, 4), "NW-KCK": (12, 5), "NW-CLT": (0, 7)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-CORO-4X8-4", "family": "Substrate", "brand": "SignBoard",
     "series": "Coroplast", "desc": "Coroplast Corrugated Plastic 4x8 4mm White",
     "category": "substrate", "compatible_group": "coroplast_4mm",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_mm": 4, "color": "White"},
     "list_cents": 1800, "account_cents": 1200, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 25, "unit_price_cents": 995}],
     "stock": {"NW-PDX": (80, 2), "NW-KCK": (100, 4), "NW-CLT": (60, 6)},
     "purchase_unit": "sheet"},
    {"vendor": "northwind_signworks", "sku": "NW-CORO-2X4-4", "family": "Substrate", "brand": "SignBoard",
     "series": "Coroplast", "desc": "Coroplast Corrugated Plastic 2x4 4mm White",
     "category": "substrate", "compatible_group": "coroplast_4mm",
     "variant": {"width_inches": 24, "height_inches": 48, "thickness_mm": 4, "color": "White"},
     "list_cents": 895, "account_cents": 595, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 50, "unit_price_cents": 495}],
     "stock": {"NW-PDX": (120, 2), "NW-KCK": (150, 4), "NW-CLT": (100, 6)},
     "purchase_unit": "sheet"},
    {"vendor": "northwind_signworks", "sku": "NW-PVC-4X8-3", "family": "Substrate", "brand": "SignBoard",
     "series": "FoamPVC", "desc": "FoamPVC 4x8 3mm White",
     "category": "substrate", "compatible_group": "foam_pvc_3mm",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_mm": 3, "color": "White"},
     "list_cents": 3500, "account_cents": 2500, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 10, "unit_price_cents": 2200}],
     "stock": {"NW-PDX": (25, 3), "NW-KCK": (20, 5), "NW-CLT": (8, 7)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-PVC-4X8-6", "family": "Substrate", "brand": "SignBoard",
     "series": "FoamPVC", "desc": "FoamPVC 4x8 6mm White",
     "category": "substrate", "compatible_group": "foam_pvc_6mm",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_mm": 6, "color": "White"},
     "list_cents": 5900, "account_cents": 4500, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (12, 4), "NW-KCK": (8, 5), "NW-CLT": (0, 7)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-MDO-4X8", "family": "Substrate", "brand": "SignBoard",
     "series": "MDO Plywood", "desc": "MDO Plywood 4x8 1/2\" 2-Side",
     "category": "substrate", "compatible_group": "mdo",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_mm": 12.7},
     "list_cents": 6900, "account_cents": 5500, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (18, 4), "NW-KCK": (10, 6), "NW-CLT": (6, 8)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-MDO-4X10", "family": "Substrate", "brand": "SignBoard",
     "series": "MDO Plywood", "desc": "MDO Plywood 4x10 3/4\" 2-Side",
     "category": "substrate", "compatible_group": "mdo",
     "variant": {"width_inches": 48, "height_inches": 120, "thickness_mm": 19.05},
     "list_cents": 12500, "account_cents": 9900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (5, 5), "NW-KCK": (4, 6), "NW-CLT": (0, 8)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-ACR-4X8-125", "family": "Substrate", "brand": "SignBoard",
     "series": "Acrylic", "desc": "Cast Acrylic 4x8 1/8\" Clear",
     "category": "substrate", "compatible_group": "acrylic_125",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_inches": 0.125, "color": "Clear"},
     "list_cents": 9500, "account_cents": 7900, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (10, 4), "NW-KCK": (6, 5), "NW-CLT": (3, 8)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-ACR-4X8-250", "family": "Substrate", "brand": "SignBoard",
     "series": "Acrylic", "desc": "Cast Acrylic 4x8 1/4\" Clear",
     "category": "substrate", "compatible_group": "acrylic_250",
     "variant": {"width_inches": 48, "height_inches": 96, "thickness_inches": 0.250, "color": "Clear"},
     "list_cents": 15500, "account_cents": 12500, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"NW-PDX": (6, 5), "NW-KCK": (4, 6), "NW-CLT": (0, 8)},
     "purchase_unit": "sheet", "freight_class": "ltl"},
    {"vendor": "northwind_signworks", "sku": "NW-CORR-4X8", "family": "Substrate", "brand": "SignBoard",
     "series": "Corrugated Cardboard", "desc": "Heavy-Duty Corrugated Cardboard 4x8 Single-Wall",
     "category": "substrate", "compatible_group": "corrugated_cardboard",
     "variant": {"width_inches": 48, "height_inches": 96},
     "list_cents": 750, "account_cents": 500, "package_qty": 5, "moq": 5,
     "breaks": [{"min_qty": 50, "unit_price_cents": 395}],
     "stock": {"NW-PDX": (60, 2), "NW-KCK": (80, 4), "NW-CLT": (40, 6)},
     "purchase_unit": "sheet"},
]

# Hardware / shop supplies — 11 SKUs.
HARDWARE_ROWS: list[dict[str, Any]] = [
    {"vendor": "redwood_hardware", "sku": "RH-GRM-38-100", "family": "Hardware", "brand": "Redwood",
     "series": "Grommets", "desc": "Brass Grommet Pack 3/8\" (100 count)",
     "category": "hardware", "compatible_group": "grommet_38",
     "variant": {"size_inches": 0.375, "count_per_pack": 100, "material": "Brass"},
     "list_cents": 2900, "account_cents": 2200, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 6, "unit_price_cents": 1900}],
     "stock": {"RH-RNO": (25, 2)}, "purchase_unit": "package"},
    {"vendor": "redwood_hardware", "sku": "RH-ZIP-8-100", "family": "Hardware", "brand": "Redwood",
     "series": "ZipTies", "desc": "Nylon Zip Tie 8\" Black (100 count)",
     "category": "hardware", "compatible_group": "zip_tie_8",
     "variant": {"length_inches": 8, "color": "Black", "count_per_pack": 100},
     "list_cents": 950, "account_cents": 695, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 10, "unit_price_cents": 550}],
     "stock": {"RH-RNO": (60, 2)}, "purchase_unit": "package"},
    {"vendor": "redwood_hardware", "sku": "RH-ZIP-11-100", "family": "Hardware", "brand": "Redwood",
     "series": "ZipTies", "desc": "Nylon Zip Tie 11\" Black (100 count)",
     "category": "hardware", "compatible_group": "zip_tie_11",
     "variant": {"length_inches": 11, "color": "Black", "count_per_pack": 100},
     "list_cents": 1250, "account_cents": 895, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 10, "unit_price_cents": 725}],
     "stock": {"RH-RNO": (40, 2)}, "purchase_unit": "package"},
    {"vendor": "redwood_hardware", "sku": "RH-SQG-4", "family": "Supplies", "brand": "Redwood",
     "series": "Squeegee", "desc": "4\" Vinyl Squeegee Firm",
     "category": "supplies", "compatible_group": "squeegee_firm",
     "variant": {"length_inches": 4, "hardness": "firm"},
     "list_cents": 495, "account_cents": 350, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 12, "unit_price_cents": 275}],
     "stock": {"RH-RNO": (100, 1)}, "purchase_unit": "each"},
    {"vendor": "redwood_hardware", "sku": "RH-SQG-FELT", "family": "Supplies", "brand": "Redwood",
     "series": "Squeegee", "desc": "Adhesive Felt Sleeves for 4\" Squeegee (10 pack)",
     "category": "supplies", "compatible_group": "squeegee_felt",
     "variant": {"count_per_pack": 10},
     "list_cents": 895, "account_cents": 595, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"RH-RNO": (50, 1)}, "purchase_unit": "package"},
    {"vendor": "redwood_hardware", "sku": "RH-KNIFE-45", "family": "Supplies", "brand": "Redwood",
     "series": "PlotterBlade", "desc": "Plotter Knife Blade 45° (5 pack)",
     "category": "supplies", "compatible_group": "plotter_blade_45",
     "variant": {"angle_deg": 45, "count_per_pack": 5},
     "list_cents": 2900, "account_cents": 2100, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 5, "unit_price_cents": 1700}],
     "stock": {"RH-RNO": (30, 1)}, "purchase_unit": "package"},
    {"vendor": "redwood_hardware", "sku": "RH-KNIFE-60", "family": "Supplies", "brand": "Redwood",
     "series": "PlotterBlade", "desc": "Plotter Knife Blade 60° (5 pack)",
     "category": "supplies", "compatible_group": "plotter_blade_60",
     "variant": {"angle_deg": 60, "count_per_pack": 5},
     "list_cents": 3300, "account_cents": 2400, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 5, "unit_price_cents": 1900}],
     "stock": {"RH-RNO": (20, 1)}, "purchase_unit": "package"},
    {"vendor": "redwood_hardware", "sku": "RH-CLN-QT", "family": "Supplies", "brand": "Redwood",
     "series": "PrepClean", "desc": "Surface Prep Cleaner Concentrate 1 qt",
     "category": "supplies", "compatible_group": "surface_cleaner",
     "variant": {"size_ounces": 32},
     "list_cents": 1150, "account_cents": 795, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"RH-RNO": (25, 1)}, "purchase_unit": "each"},
    {"vendor": "redwood_hardware", "sku": "RH-IPA-GAL", "family": "Supplies", "brand": "Redwood",
     "series": "IPA", "desc": "Isopropyl Alcohol 99% 1 gal",
     "category": "supplies", "compatible_group": "ipa_99",
     "variant": {"purity": "99%", "size_gallons": 1},
     "list_cents": 2900, "account_cents": 2200, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 4, "unit_price_cents": 1900}],
     "stock": {"RH-RNO": (12, 1)}, "purchase_unit": "each"},
    {"vendor": "redwood_hardware", "sku": "RH-MASK-2", "family": "Supplies", "brand": "Redwood",
     "series": "MaskingTape", "desc": "Blue Masking Tape 2\" x 60yd",
     "category": "supplies", "compatible_group": "masking_tape_2",
     "variant": {"width_inches": 2, "length_yards": 60, "color": "Blue"},
     "list_cents": 750, "account_cents": 495, "package_qty": 1, "moq": 1,
     "breaks": [{"min_qty": 12, "unit_price_cents": 395}],
     "stock": {"RH-RNO": (48, 1)}, "purchase_unit": "each"},
    {"vendor": "redwood_hardware", "sku": "RH-GLOVE-M", "family": "Supplies", "brand": "Redwood",
     "series": "NitrileGloves", "desc": "Nitrile Gloves Medium (100 count)",
     "category": "supplies", "compatible_group": "nitrile_gloves_m",
     "variant": {"size": "M", "count_per_pack": 100},
     "list_cents": 1250, "account_cents": 895, "package_qty": 1, "moq": 1,
     "breaks": [], "stock": {"RH-RNO": (30, 1)}, "purchase_unit": "package"},
]


def _expand_apparel(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a style row into color × size variant SKUs."""
    out: list[dict[str, Any]] = []
    idx = 0
    for color in row["colors"]:
        for size in row["sizes"]:
            sku = f"{row['family']}-{color[:3].upper()}-{size}"
            variant_stock: dict[str, tuple[int, int]] = {}
            for wh, stock_list in row["stock"].items():
                qty = stock_list[idx] if idx < len(stock_list) else 0
                variant_stock[wh] = (qty, row["lead"][wh])
            out.append({
                "vendor": row["vendor"],
                "sku": sku,
                "family": row["family"],
                "brand": row["brand"],
                "series": row["series"],
                "desc": f"{row['series']} — {color} — {size}",
                "category": "apparel",
                "compatible_group": row.get("compatible_group"),
                "variant": {"color": color, "size": size, "brand_style": row["family"]},
                "list_cents": row["list_cents"],
                "account_cents": row["account_cents"],
                "package_qty": row["package_qty"],
                "moq": row["moq"],
                "breaks": row["breaks"],
                "stock": variant_stock,
                "purchase_unit": "each",
            })
            idx += 1
    return out


def _all_catalog_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for style in APPAREL_STYLES:
        rows.extend(_expand_apparel(style))
    for r in VINYL_ROWS:
        # Vinyl rows already expose {stock: {wh: (qty, lead)}}
        rows.append(r)
    for r in SUBSTRATE_ROWS:
        rows.append(r)
    for r in HARDWARE_ROWS:
        rows.append(r)
    return rows


class TestSupplierAdapter(SupplierConnectorBase):
    """Deterministic full-capability adapter. Owns the ~80-SKU synthetic catalog."""

    connector_key = "test_adapter"
    tier = "test_adapter"
    capabilities = {
        ConnectorCapability.SEARCH,
        ConnectorCapability.PRODUCT,
        ConnectorCapability.VARIANTS,
        ConnectorCapability.ACCOUNT_PRICE,
        ConnectorCapability.INVENTORY,
        ConnectorCapability.SHIPPING_QUOTE,
        ConnectorCapability.SUBMIT_ORDER,
        ConnectorCapability.RETRIEVE_ORDER,
        ConnectorCapability.TRACKING,
        ConnectorCapability.CANCEL,
    }

    # ---- Seed data ----
    async def seed_tenant(self, *, tenant_id: str, reset: bool = False) -> dict[str, int]:
        """Idempotent seed of all synthetic vendors + warehouses + products
        for a specific tenant. Safe to re-run; upserts by deterministic id.
        """
        stats = {"vendors": 0, "warehouses": 0, "products": 0, "stock": 0}
        if reset:
            for coll in ("vendors", "supplier_warehouses", "supplier_products", "supplier_product_stock"):
                await db[coll].delete_many({"tenant_id": tenant_id, "seed_source": "test_adapter"})
        # Vendors + warehouses
        vendor_id_by_key: dict[str, str] = {}
        wh_id_by_code: dict[str, str] = {}
        for v in SYNTHETIC_VENDORS:
            vid = _det_id("ven", tenant_id, v["key"])
            vendor_id_by_key[v["key"]] = vid
            vendor_doc = {
                "id": vid, "tenant_id": tenant_id, "name": v["name"], "display_name": v["name"],
                "connector_key": v["connector_key"], "connector_tier": v["tier"],
                "categories": v["categories"], "preferred": v["preferred"],
                "active": True, "seed_source": "test_adapter",
                "created_at": utc_now().isoformat(), "updated_at": utc_now().isoformat(),
            }
            await db.vendors.update_one({"id": vid}, {"$set": vendor_doc}, upsert=True)
            stats["vendors"] += 1
            for wh in v["warehouses"]:
                wid = _det_id("wh", tenant_id, v["key"], wh["code"])
                wh_id_by_code[wh["code"]] = wid
                wh_doc = {
                    "id": wid, "tenant_id": tenant_id, "vendor_id": vid,
                    "code": wh["code"], "name": wh["name"], "region": wh.get("region"),
                    "city": wh.get("city"), "state": wh.get("state"),
                    "base_ship_cost_cents": wh["base_ship_cost_cents"],
                    "per_item_ship_cost_cents": wh["per_item_ship_cost_cents"],
                    "freight_multiplier": wh.get("freight_multiplier", 1.0),
                    "handling_fee_cents": wh.get("handling_fee_cents", 0),
                    "active": True, "seed_source": "test_adapter",
                    "created_at": utc_now().isoformat(), "updated_at": utc_now().isoformat(),
                }
                await db.supplier_warehouses.update_one({"id": wid}, {"$set": wh_doc}, upsert=True)
                stats["warehouses"] += 1
        # Products + stock
        for row in _all_catalog_rows():
            vid = vendor_id_by_key[row["vendor"]]
            pid = _det_id("sp", tenant_id, row["vendor"], row["sku"])
            product_doc = {
                "id": pid, "tenant_id": tenant_id, "vendor_id": vid,
                "supplier_sku": row["sku"], "manufacturer": row["brand"],
                "brand": row["brand"], "series": row["series"], "family": row["family"],
                "description": row["desc"], "category": row["category"],
                "variant": row.get("variant", {}),
                "purchase_unit": row.get("purchase_unit", "each"),
                "package_qty": row.get("package_qty", 1),
                "minimum_order_qty": row.get("moq", 0),
                "quantity_breaks": row.get("breaks", []),
                "list_price_cents": row["list_cents"],
                "account_price_cents": row["account_cents"],
                "price_effective_at": utc_now().isoformat(),
                "compatible_group": row.get("compatible_group"),
                "incompatible_with": row.get("incompatible_with", []),
                "freight_class": row.get("freight_class"),
                "active": True,
                "discontinued": bool(row.get("discontinued", False)),
                "seed_source": "test_adapter", "seed_ref": row["sku"],
                "last_synced_at": utc_now().isoformat(),
                "created_at": utc_now().isoformat(), "updated_at": utc_now().isoformat(),
            }
            await db.supplier_products.update_one({"id": pid}, {"$set": product_doc}, upsert=True)
            stats["products"] += 1
            for wh_code, stock in row["stock"].items():
                wid = wh_id_by_code.get(wh_code)
                if not wid:
                    continue
                qty, lead = stock
                stock_id = _det_id("sps", tenant_id, pid, wh_code)
                stock_doc = {
                    "id": stock_id, "tenant_id": tenant_id, "vendor_id": vid,
                    "supplier_product_id": pid, "warehouse_id": wid,
                    "available_qty": int(qty), "lead_time_days": int(lead),
                    "last_synced_at": utc_now().isoformat(),
                    "created_at": utc_now().isoformat(), "updated_at": utc_now().isoformat(),
                }
                await db.supplier_product_stock.update_one(
                    {"id": stock_id}, {"$set": stock_doc}, upsert=True
                )
                stats["stock"] += 1
        stats["synthetic"] = True
        return stats

    # ---- Interface methods ----
    async def search_catalog(self, *, tenant_id: str, vendor_id: str, query: str,
                             category: Optional[str] = None, limit: int = 50) -> list[dict]:
        filt: dict[str, Any] = {"tenant_id": tenant_id, "active": True}
        if vendor_id:
            filt["vendor_id"] = vendor_id
        if category:
            filt["category"] = category
        if query:
            filt["$or"] = [
                {"description": {"$regex": query, "$options": "i"}},
                {"supplier_sku": {"$regex": query, "$options": "i"}},
                {"brand": {"$regex": query, "$options": "i"}},
                {"series": {"$regex": query, "$options": "i"}},
                {"family": {"$regex": query, "$options": "i"}},
            ]
        cur = db.supplier_products.find(filt, {"_id": 0}).limit(limit)
        return [serialize_doc(d) async for d in cur]

    async def get_product(self, *, tenant_id: str, vendor_id: str, supplier_product_id: str) -> dict:
        doc = await db.supplier_products.find_one(
            {"tenant_id": tenant_id, "id": supplier_product_id}, {"_id": 0}
        )
        return serialize_doc(doc) if doc else {}

    async def get_variants(self, *, tenant_id: str, vendor_id: str, family_key: str) -> list[dict]:
        cur = db.supplier_products.find(
            {"tenant_id": tenant_id, "family": family_key, "active": True}, {"_id": 0}
        )
        return [serialize_doc(d) async for d in cur]

    async def get_account_price(self, *, tenant_id: str, vendor_id: str, supplier_product_id: str,
                                quantity: int) -> dict:
        prod = await db.supplier_products.find_one(
            {"tenant_id": tenant_id, "id": supplier_product_id}, {"_id": 0}
        )
        if not prod:
            return {"unit_price_cents": 0, "band": None}
        price = int(prod.get("account_price_cents", 0))
        band = None
        for b in prod.get("quantity_breaks", []) or []:
            if quantity >= int(b["min_qty"]):
                price = int(b["unit_price_cents"])
                band = b
        return {"unit_price_cents": price, "band": band,
                "list_price_cents": int(prod.get("list_price_cents", 0)),
                "package_qty": int(prod.get("package_qty", 1)),
                "minimum_order_qty": int(prod.get("minimum_order_qty", 0))}

    async def get_inventory(self, *, tenant_id: str, vendor_id: str, supplier_product_id: str) -> list[dict]:
        cur = db.supplier_product_stock.find(
            {"tenant_id": tenant_id, "supplier_product_id": supplier_product_id}, {"_id": 0}
        )
        stocks = [serialize_doc(d) async for d in cur]
        # Attach warehouse metadata for the caller.
        for s in stocks:
            wh = await db.supplier_warehouses.find_one({"id": s["warehouse_id"]}, {"_id": 0})
            s["warehouse"] = serialize_doc(wh) if wh else None
        return stocks

    async def get_shipping_quote(self, *, tenant_id: str, vendor_id: str, warehouse_id: str,
                                 line_count: int, weight_lbs: float = 0.0) -> dict:
        wh = await db.supplier_warehouses.find_one(
            {"tenant_id": tenant_id, "id": warehouse_id}, {"_id": 0}
        )
        if not wh:
            return {"cost_cents": 0, "handling_cents": 0, "rate_type": RATE_ESTIMATED,
                    "warehouse_id": warehouse_id, "message": "unknown_warehouse"}
        base = int(wh["base_ship_cost_cents"])
        per_line = int(wh["per_item_ship_cost_cents"]) * max(int(line_count), 0)
        cost = int(round((base + per_line) * float(wh.get("freight_multiplier", 1.0))))
        return {
            "cost_cents": cost,
            "handling_cents": int(wh.get("handling_fee_cents", 0)),
            "rate_type": RATE_ESTIMATED,
            "warehouse_id": warehouse_id,
            "warehouse_code": wh.get("code"),
        }

    async def create_supplier_order(self, *, tenant_id: str, vendor_id: str,
                                    purchase_order: dict, idempotency_key: str,
                                    actor_user_id: Optional[str] = None) -> dict:
        if not idempotency_key:
            raise ValueError("idempotency_key_required")
        # Replay -> return existing log
        existing = await db.supplier_order_log.find_one(
            {"tenant_id": tenant_id, "idempotency_key": idempotency_key}, {"_id": 0}
        )
        if existing:
            return {"status": "duplicate_replay", "log": serialize_doc(existing)}
        supplier_order_id = _det_id("supord", tenant_id, idempotency_key)
        log_doc = {
            "id": _det_id("sol", tenant_id, idempotency_key),
            "tenant_id": tenant_id, "vendor_id": vendor_id,
            "purchase_order_id": purchase_order.get("id", ""),
            "idempotency_key": idempotency_key,
            "request_id": _det_id("req", tenant_id, idempotency_key),
            "submitted_at": utc_now().isoformat(),
            "submitted_by_user_id": actor_user_id,
            "request_payload": {"lines": len(purchase_order.get("lines", []))},
            "response_status": "accepted",
            "response_payload": {"supplier_order_id": supplier_order_id, "eta_days": 3},
            "supplier_order_id": supplier_order_id,
            "tracking_number": f"SGY-TRK-{supplier_order_id[-6:].upper()}",
            "tracking_status": "acknowledged",
            "created_at": utc_now().isoformat(), "updated_at": utc_now().isoformat(),
        }
        await db.supplier_order_log.insert_one(log_doc)
        return {"status": "accepted", "log": serialize_doc(log_doc)}

    async def retrieve_supplier_order(self, *, tenant_id: str, vendor_id: str,
                                      supplier_order_id: str) -> dict:
        doc = await db.supplier_order_log.find_one(
            {"tenant_id": tenant_id, "supplier_order_id": supplier_order_id}, {"_id": 0}
        )
        return serialize_doc(doc) if doc else {}

    async def retrieve_tracking(self, *, tenant_id: str, vendor_id: str,
                                supplier_order_id: str) -> dict:
        doc = await db.supplier_order_log.find_one(
            {"tenant_id": tenant_id, "supplier_order_id": supplier_order_id}, {"_id": 0}
        )
        if not doc:
            return {"status": "unknown"}
        # Deterministic status progression based on how long ago the order was submitted (test)
        return {
            "supplier_order_id": supplier_order_id,
            "tracking_number": doc.get("tracking_number"),
            "status": doc.get("tracking_status", "in_transit"),
            "last_polled_at": utc_now().isoformat(),
        }

    async def cancel_order(self, *, tenant_id: str, vendor_id: str,
                           supplier_order_id: str, reason: Optional[str] = None) -> dict:
        res = await db.supplier_order_log.update_one(
            {"tenant_id": tenant_id, "supplier_order_id": supplier_order_id},
            {"$set": {"response_status": "cancelled", "tracking_status": "cancelled",
                      "response_payload.cancel_reason": reason,
                      "updated_at": utc_now().isoformat()}}
        )
        return {"cancelled": res.modified_count > 0, "supplier_order_id": supplier_order_id}

"""SignGuy AI Starter Default Pack.

Single source of truth for the STARTER template.
Every new tenant clones this pack into their own pricing_settings document.
Editing here does NOT retroactively affect existing tenants.

Strategy for values:
- MVP baseline anchors from the SignGuy AI product spec take priority.
- Where the spec is silent, we fall back to tested defaults from the original
  Pricing Foundation (documented in PRICING_DEFAULTS_AUDIT.md).
- Money is stored as float dollars in this seed for readability; calculator
  converts to internal Decimal for math to avoid float drift.
"""
from __future__ import annotations

from typing import Any, Optional

STARTER_DEFAULT_VERSION = "1.1.0"

CATEGORY_IDS = [
    "banners", "rigid_signs", "cut_vinyl", "digital_print",
    "vehicle_graphics", "apparel", "services", "promotional", "custom",
]

CATEGORY_META: dict[str, dict[str, str]] = {
    "banners":         {"name": "Banners",           "description": "Vinyl banners, mesh, blockout. Priced by area with common finishing options."},
    "rigid_signs":     {"name": "Rigid Signs",       "description": "Yard signs, coroplast, ACM, aluminum, foam board."},
    "cut_vinyl":       {"name": "Cut Vinyl",         "description": "Decals, lettering, wall graphics. Priced by area with masking + weeding."},
    "digital_print":   {"name": "Digital Print",     "description": "Posters, adhesive prints, wall/floor graphics, laminated prints."},
    "vehicle_graphics":{"name": "Vehicle Graphics",  "description": "Door lettering, spot graphics, partial and full wraps."},
    "apparel":         {"name": "Apparel",           "description": "T-shirts, hoodies, hats. Decorated with HTV, DTF, screen print, embroidery."},
    "services":        {"name": "Services",          "description": "Design, install, removal, consultation, project management."},
    "promotional":     {"name": "Promotional",       "description": "Vendor-sourced promo items with markup and setup fees."},
    "custom":          {"name": "Custom",            "description": "One-off projects. Cost + labor + profit with a fallback markup."},
}

SHOP_DEFAULTS: dict[str, float] = {
    # Global Labor Rates — EC09 controlling document exact values (2026-02)
    "production_hourly_rate": 28.00,
    "design_hourly_rate": 85.00,
    "install_hourly_rate": 95.00,
    "removal_hourly_rate": 65.00,
    "travel_hourly_rate": 45.00,
    "admin_hourly_rate": 35.00,
    "consultation_hourly_rate": 110.00,
    "site_survey_hourly_rate": 95.00,
    "finishing_hourly_rate": 28.00,
    # Global Markup & Overhead — EC09 controlling document exact values
    "default_overhead_percent": 15.00,
    "target_profit_margin_percent": 40.00,
    "default_markup_multiplier": 2.5,
    # Not given an explicit global number by the EC09 controlling document —
    # kept as the pre-existing, tenant-editable shop-level fallback that
    # categories reference as "Pricing Foundation" defaults when they don't
    # define their own (see EC9 preflight Phase 9B report for detail).
    "minimum_order_amount": 25.00,
    "deposit_percentage": 50.00,
    "default_waste_percent": 10.0,
    "rush_fee_percent": 25.0,
    # New in Phase 9B — EC09 references these as "Pricing Foundation install
    # minimum" / "Pricing Foundation setup fee" fallbacks used by several
    # categories; the document does not give a single global dollar amount,
    # so these are seeded at 0.00 (no fee unless the shop configures one) and
    # remain fully editable.
    "install_minimum_charge": 0.00,
    "setup_fee_default": 0.00,
    # Not present in the EC09 document as a distinct line item (overhead is
    # the only shop-level loading percentage defined there); kept separate
    # from overhead per the Phase 9B requirement list, seeded at 0.00, editable.
    "labor_burden_percent": 0.0,
    # EC9 Phase 9E-1 — EC09 controlling document: "file cleanup fee defaults: $20"
    "file_cleanup_fee_default": 20.00,
}

# EC9 Phase 9E-1 — shared complexity/install multiplier scales (EC09 controlling
# document, Global Definitions). Every flat/square-foot category uses the same
# 4-level scale for Design Complexity and (a differently-labelled but
# identically-valued) Install Complexity scale.
DESIGN_COMPLEXITY_MULTIPLIERS: dict[str, float] = {"simple": 1.00, "medium": 1.25, "complex": 1.50, "extreme": 2.00}
INSTALL_COMPLEXITY_MULTIPLIERS: dict[str, float] = {"easy": 1.00, "medium": 1.25, "difficult": 1.50, "extreme": 2.00}

# EC9 Phase 9E-1 — exact per-category quantity discount tiers (EC09 controlling
# document). Each tuple is (min_qty, max_qty_or_None, discount_percent).
FLAT_SQFT_QUANTITY_TIERS: dict[str, list[tuple[int, Optional[int], float]]] = {
    "banners":       [(1, 2, 0.0), (3, 9, 5.0), (10, 24, 10.0), (25, None, 15.0)],
    "rigid_signs":   [(1, 4, 0.0), (5, 24, 5.0), (25, 99, 10.0), (100, None, 15.0)],
    "digital_print": [(1, 4, 0.0), (5, 24, 5.0), (25, 99, 10.0), (100, None, 15.0)],
    "cut_vinyl":     [(1, 5, 0.0), (6, 24, 5.0), (25, 99, 10.0), (100, None, 15.0)],
}

# EC9 Phase 9E-2 — Apparel garment quantity/placement pricing tables and
# decoration method configs (EC09 controlling document, Apparel section,
# exact values). Every tier row is {min_qty, max_qty, front, back, combo}:
# `front`/`back` map to "Front Small"/"Back Large" (garments) or "Front
# Only"/"Side-Back" (hats); `combo` maps to "Front + Back" / "Front +
# Side/Back". Stored under category_defaults so every value stays
# tenant-editable through the existing Pricing Foundation category-update
# endpoints (no separate table lives outside category_defaults).
def _tiers(*rows: tuple[int, Optional[int], float, float, float]) -> list[dict[str, Any]]:
    return [{"min_qty": lo, "max_qty": hi, "front": f, "back": b, "combo": c} for lo, hi, f, b, c in rows]


APPAREL_GARMENTS: dict[str, dict[str, Any]] = {
    "short_sleeve_tee": {"label": "Short Sleeve Tee", "is_hat": False, "brands": {
        "gildan_5000": {"label": "Gildan 5000", "blank_cost": 3.25, "tiers": _tiers(
            (1, 4, 12.00, 13.50, 17.00), (5, 24, 10.50, 12.00, 15.00), (25, 49, 9.00, 10.50, 14.00),
            (50, 99, 8.25, 9.50, 13.00), (100, None, 7.75, 9.00, 12.50),
        )},
        "bella_3001": {"label": "Bella + Canvas 3001", "blank_cost": 5.00, "tiers": _tiers(
            (1, 4, 14.00, 15.50, 19.00), (5, 24, 12.50, 14.00, 17.00), (25, 49, 11.00, 12.50, 16.00),
            (50, 99, 10.25, 11.75, 15.00), (100, None, 9.75, 11.25, 14.50),
        )},
    }},
    "long_sleeve_tee": {"label": "Long Sleeve Tee", "is_hat": False, "brands": {
        "gildan_2400": {"label": "Gildan 2400", "blank_cost": 6.00, "tiers": _tiers(
            (1, 4, 15.00, 16.50, 20.00), (5, 24, 13.50, 15.00, 18.00), (25, 49, 12.00, 13.50, 17.00),
            (50, 99, 11.25, 12.50, 16.00), (100, None, 10.75, 12.00, 15.50),
        )},
        "bella_3501": {"label": "Bella + Canvas 3501", "blank_cost": 8.00, "tiers": _tiers(
            (1, 4, 17.00, 18.50, 22.00), (5, 24, 15.50, 17.00, 20.00), (25, 49, 14.00, 15.50, 19.00),
            (50, 99, 13.25, 14.75, 18.00), (100, None, 12.75, 14.25, 17.50),
        )},
    }},
    "crewneck_sweatshirt": {"label": "Crewneck Sweatshirt", "is_hat": False, "brands": {
        "gildan_18000": {"label": "Gildan 18000", "blank_cost": 9.00, "tiers": _tiers(
            (1, 4, 18.00, 19.50, 23.00), (5, 24, 16.50, 18.00, 21.00), (25, 49, 15.00, 16.50, 20.00),
            (50, 99, 14.25, 15.50, 19.00), (100, None, 13.75, 15.00, 18.50),
        )},
        "bella_3901": {"label": "Bella + Canvas 3901", "blank_cost": 11.00, "tiers": _tiers(
            (1, 4, 20.00, 21.50, 25.00), (5, 24, 18.50, 20.00, 23.00), (25, 49, 17.00, 18.50, 22.00),
            (50, 99, 16.25, 17.75, 21.00), (100, None, 15.75, 17.25, 20.50),
        )},
    }},
    "hoodie": {"label": "Hoodie", "is_hat": False, "brands": {
        "gildan_18500": {"label": "Gildan 18500", "blank_cost": 13.00, "tiers": _tiers(
            (1, 4, 23.00, 24.50, 28.00), (5, 24, 21.50, 23.00, 26.00), (25, 49, 20.00, 21.50, 25.00),
            (50, 99, 19.25, 20.50, 24.00), (100, None, 18.75, 20.00, 23.50),
        )},
        "bella_3719": {"label": "Bella + Canvas 3719", "blank_cost": 17.00, "tiers": _tiers(
            (1, 4, 25.00, 26.50, 30.00), (5, 24, 23.50, 25.00, 28.00), (25, 49, 22.00, 23.50, 27.00),
            (50, 99, 21.25, 22.75, 26.00), (100, None, 20.75, 22.25, 25.50),
        )},
    }},
    "polo": {"label": "Polo", "is_hat": False, "brands": {
        "gildan_8800": {"label": "Gildan 8800", "blank_cost": 6.00, "tiers": _tiers(
            (1, 4, 14.00, 15.50, 19.00), (5, 24, 12.50, 14.00, 17.00), (25, 49, 11.00, 12.50, 16.00),
            (50, 99, 10.25, 11.75, 15.00), (100, None, 9.75, 11.25, 14.50),
        )},
        "bella_3415": {"label": "Bella + Canvas 3415", "blank_cost": 8.50, "tiers": _tiers(
            (1, 4, 16.00, 17.50, 21.00), (5, 24, 14.50, 16.00, 19.00), (25, 49, 13.00, 14.50, 18.00),
            (50, 99, 12.25, 13.75, 17.00), (100, None, 11.75, 13.25, 16.50),
        )},
    }},
    "standard_cap": {"label": "Standard Cap", "is_hat": True, "blank_cost": 4.00, "tiers": _tiers(
        (1, 4, 12.00, 13.00, 15.00), (5, 24, 11.00, 12.00, 14.00), (25, 49, 10.00, 11.00, 13.00),
        (50, 99, 9.50, 10.50, 12.50), (100, None, 9.00, 10.00, 12.00),
    )},
    "premium_cap": {"label": "Premium Cap", "is_hat": True, "blank_cost": 6.00, "tiers": _tiers(
        (1, 4, 14.00, 15.00, 17.00), (5, 24, 13.00, 14.00, 16.00), (25, 49, 12.00, 13.00, 15.00),
        (50, 99, 11.50, 12.50, 14.50), (100, None, 11.00, 12.00, 14.00),
    )},
    # EC09 controlling document lists "Standard Cap / Visor" as a single
    # shared tier table — the Visor has its own blank cost but reuses the
    # Standard Cap sell-price tiers verbatim.
    "visor": {"label": "Visor", "is_hat": True, "blank_cost": 4.00, "tiers": _tiers(
        (1, 4, 12.00, 13.00, 15.00), (5, 24, 11.00, 12.00, 14.00), (25, 49, 10.00, 11.00, 13.00),
        (50, 99, 9.50, 10.50, 12.50), (100, None, 9.00, 10.00, 12.00),
    )},
}

# EC09 controlling document — Apparel Decoration Method configs. `table_based`
# methods (HTV, Screen Print Transfer) are "currently fully priced" via the
# garment tier table above; the other 7 methods have full foundation/model
# support (selectable now, cost-plus priced from these constants) per the
# document's explicit instruction that they "must not be hard-coded in a way
# that prevents later method-specific pricing tables" being added.
APPAREL_DECORATION_METHODS: dict[str, dict[str, Any]] = {
    "htv":                  {"label": "HTV",                    "setup_fee": 10.00, "material_cost_type": "per_color_per_piece", "material_cost_rate": 0.50, "min_sell_per_piece": None, "table_based": True},
    "screen_print_transfer":{"label": "Screen Print Transfer",   "setup_fee": 15.00, "material_cost_type": "per_color_per_piece", "material_cost_rate": 0.35, "min_sell_per_piece": None, "table_based": True},
    "dtf_transfer":         {"label": "DTF Transfer",            "setup_fee": 10.00, "material_cost_type": "per_sqin",            "material_cost_rate": 0.03, "min_sell_per_piece": None, "table_based": False},
    "direct_screen_print":  {"label": "Direct Screen Print",     "setup_fee": 30.00, "setup_fee_per_color": True, "material_cost_type": "per_color_per_piece", "material_cost_rate": 0.25, "min_sell_per_piece": 5.00, "table_based": False},
    "embroidery":           {"label": "Embroidery",               "setup_fee": 25.00, "material_cost_type": "per_1000_stitches",   "material_cost_rate": 0.75, "min_sell_per_piece": 6.00, "table_based": False},
    "dtg":                  {"label": "DTG",                      "setup_fee": 5.00,  "material_cost_type": "per_piece",           "material_cost_rate": 2.50, "min_sell_per_piece": 8.00, "table_based": False},
    "patch_emblem":         {"label": "Patch / Emblem",           "setup_fee": 0.00,  "material_cost_type": "per_piece",           "material_cost_rate": 3.00, "min_sell_per_piece": 4.00, "table_based": False},
    "sublimation":          {"label": "Sublimation",              "setup_fee": 10.00, "material_cost_type": "per_sqin",            "material_cost_rate": 0.04, "min_sell_per_piece": 5.00, "table_based": False},
    "specialty_custom":     {"label": "Specialty / Custom",       "setup_fee": 20.00, "material_cost_type": "per_piece",           "material_cost_rate": 3.00, "min_sell_per_piece": 6.00, "table_based": False},
}

# Reusable material catalogs. Only a compact, opinionated subset of the
# original repo’s dozens of materials — enough for the MVP calculator.
MATERIALS: dict[str, dict[str, Any]] = {
    # key: {name, category, cost_per_sqft, sell_per_sqft (optional)}
    "banner_13oz":                {"name": "13 oz Banner",            "category": "banners",       "cost_per_sqft": 0.85, "sell_per_sqft": 8.00},
    "banner_18oz":                {"name": "18 oz Banner",            "category": "banners",       "cost_per_sqft": 1.25, "sell_per_sqft": 10.00},
    "banner_mesh":                {"name": "Mesh Banner",             "category": "banners",       "cost_per_sqft": 1.40, "sell_per_sqft": 11.00},
    "banner_blockout":            {"name": "Blockout Banner",         "category": "banners",       "cost_per_sqft": 1.65, "sell_per_sqft": 12.00},

    "coroplast_4mm":              {"name": "Coroplast 4mm",           "category": "rigid_signs",   "cost_per_sqft": 0.90, "sell_per_sqft": 10.00},
    "coroplast_10mm":             {"name": "Coroplast 10mm",          "category": "rigid_signs",   "cost_per_sqft": 1.60, "sell_per_sqft": 14.00},
    "pvc_3mm":                    {"name": "PVC 3mm",                 "category": "rigid_signs",   "cost_per_sqft": 2.25, "sell_per_sqft": 16.00},
    "acm_3mm":                    {"name": "ACM / Dibond 3mm",        "category": "rigid_signs",   "cost_per_sqft": 4.25, "sell_per_sqft": 24.00},
    "aluminum_040":               {"name": "Aluminum .040",           "category": "rigid_signs",   "cost_per_sqft": 3.25, "sell_per_sqft": 18.00},
    "foamboard":                  {"name": "Foamboard 3/16\"",         "category": "rigid_signs",   "cost_per_sqft": 1.25, "sell_per_sqft": 12.00},

    "oracal_651":                 {"name": "Oracal 651",              "category": "cut_vinyl",     "cost_per_sqft": 1.25, "sell_per_sqft": 12.00},
    "oracal_751":                 {"name": "Oracal 751",              "category": "cut_vinyl",     "cost_per_sqft": 2.50, "sell_per_sqft": 15.00},
    "reflective_vinyl":           {"name": "Reflective Vinyl",        "category": "cut_vinyl",     "cost_per_sqft": 4.50, "sell_per_sqft": 22.00},

    "print_adhesive_vinyl":       {"name": "Adhesive Print Vinyl",    "category": "digital_print", "cost_per_sqft": 1.50, "sell_per_sqft": 10.00},
    "poster_paper":               {"name": "Poster Paper",            "category": "digital_print", "cost_per_sqft": 0.60, "sell_per_sqft": 6.00},
    "wall_graphic_media":         {"name": "Wall Graphic Media",      "category": "digital_print", "cost_per_sqft": 2.25, "sell_per_sqft": 14.00},
    "floor_graphic_media":        {"name": "Floor Graphic Media",     "category": "digital_print", "cost_per_sqft": 3.00, "sell_per_sqft": 20.00},

    "wrap_calendered":            {"name": "Standard Calendered Wrap Vinyl","category": "vehicle_graphics", "cost_per_sqft": 1.50, "sell_per_sqft": 9.00},
    "wrap_cast":                  {"name": "Premium Cast Wrap Vinyl", "category": "vehicle_graphics", "cost_per_sqft": 3.50, "sell_per_sqft": 18.00},
    "window_perf":                {"name": "Window Perf Film",        "category": "vehicle_graphics", "cost_per_sqft": 2.50, "sell_per_sqft": 18.00},
}


def _make_category(pricing_method: str, base_rate: float | None, minimum_charge: float,
                   markup: float, target_margin: float, waste_percent: float,
                   default_material: str | None = None, install_included: bool = False,
                   design_included: bool = False, needs_tenant_setup: bool = False,
                   extras: dict[str, Any] | None = None) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "pricing_method": pricing_method,  # "per_sqft" | "cost_plus_labor" | "common_job_prices"
        "minimum_charge": minimum_charge,
        "base_sell_rate_per_sqft": base_rate,
        "default_markup_multiplier": markup,
        "target_margin_percent": target_margin,
        "waste_percent": waste_percent,
        "default_material": default_material,
        "design_included": design_included,
        "install_included": install_included,
        "common_job_prices": {},   # tenant-editable, populated by wizard answers
        "quantity_tiers": [],
        "setup_complete": False,
        "setup_updated_at": None,
        "needs_tenant_setup": needs_tenant_setup,
    }
    if extras:
        doc.update(extras)
    return doc


CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "banners": _make_category(
        pricing_method="per_sqft", base_rate=8.00, minimum_charge=35.00,
        markup=2.35, target_margin=40.0, waste_percent=8.0,
        default_material="banner_13oz",
        extras={
            "hems_grommets_included": True,
            "grommet_sell_price_each": 0.75,
            "pole_pocket_charge_per_ft": 3.50,
            "reinforced_corners_charge": 6.00,
            "wind_slit_charge": 2.00,
            "install_available": True,
            # EC9 Phase 9E-1 additions (EC09 controlling document, Banners section)
            "min_billable_area_sqft": 4.0,
            "print_consumable_rate_per_sqft": 0.75,
            "grommet_minimum_charge": 4.00,
            "hem_charge_per_linear_ft": 0.35,
            "specialty_sewing_charge": 15.00,
            "coating_rate_per_sqft": {"none": 0.0, "matte": 0.30, "gloss": 0.35},
            "double_sided_same_side_multiplier": 1.75,
            "double_sided_different_side_multiplier": 2.00,
            "event_premium_multiplier": 1.20,
            "step_and_repeat_multiplier": 1.30,
            "design_default_hours": 0.5,
            "production_labor_hr_per_sqft": 0.10,
            "install_base_hr_per_sqft": 0.08,
            "quantity_tiers": [
                {"min_qty": 1, "max_qty": 2, "discount_percent": 0},
                {"min_qty": 3, "max_qty": 9, "discount_percent": 5},
                {"min_qty": 10, "max_qty": 24, "discount_percent": 10},
                {"min_qty": 25, "max_qty": None, "discount_percent": 15},
            ],
        },
    ),
    "rigid_signs": _make_category(
        pricing_method="per_sqft", base_rate=10.00, minimum_charge=25.00,
        markup=2.45, target_margin=41.0, waste_percent=5.0,
        default_material="coroplast_4mm",
        extras={
            "coroplast_4x4_default_sell_price": 47.00,
            "coroplast_4x8_default_sell_price": 75.00,
            "yard_sign_large_qty_each_price": 8.50,
            # EC9 Phase 9E-1 additions (EC09 controlling document, Rigid Signs section)
            "min_billable_area_sqft": 1.0,
            "graphic_method_cost_per_sqft": {"direct_print": 1.25, "mounted_print": 2.00, "cut_vinyl_applied": 1.25},
            "shape_multipliers": {"standard": 1.0, "custom_cut": 1.5, "complex_cut": 2.0},
            "finish_quality_multipliers": {"standard": 1.0, "premium": 1.25, "show_quality": 1.5},
            "thickness_multipliers": {"standard": 1.0, "heavy_duty": 1.1, "extra_heavy": 1.2},
            "double_sided_multiplier": 1.75,
            "drill_prep_charge": 3.00,
            "hardware_options": {
                "none": {"name": "None", "sell_price": 0.0},
                "h_stake": {"name": "Standard H-Stake", "sell_price": 3.50},
                "heavy_duty_stake": {"name": "Heavy-Duty Stake", "sell_price": 5.00},
            },
            "hardware_handling_labor_default": 5.00,
            "design_default_hours": 0.5,
            "production_labor_hr_per_sqft": 0.15,
            "install_base_hr_per_sqft": 0.08,
            "quantity_tiers": [
                {"min_qty": 1, "max_qty": 4, "discount_percent": 0},
                {"min_qty": 5, "max_qty": 24, "discount_percent": 5},
                {"min_qty": 25, "max_qty": 99, "discount_percent": 10},
                {"min_qty": 100, "max_qty": None, "discount_percent": 15},
            ],
        },
    ),
    "cut_vinyl": _make_category(
        pricing_method="per_sqft", base_rate=12.00, minimum_charge=25.00,
        markup=2.30, target_margin=40.0, waste_percent=10.0,
        default_material="oracal_651",
        extras={
            "cleanup_fee": 20.00, "masking_required": True,
            # EC9 Phase 9E-1 additions (EC09 controlling document, Cut Vinyl section)
            "min_billable_area_sqft": 0.5,
            "color_count_multipliers": {"1": 1.00, "2": 1.50, "3": 2.00, "4_plus": 2.50},
            "weeding_complexity_multipliers": {"simple": 1.00, "medium": 1.25, "complex": 1.50, "extreme": 2.00},
            "masking_tape_cost_per_sqft": 0.15,
            "surface_type_multipliers": {"flat": 1.00, "curved": 1.40, "awkward": 1.75},
            "production_labor_hr_per_sqft": 0.20,
            "design_default_hours": 0.5,
            "install_base_hr_per_sqft": 0.08,
            "quantity_tiers": [
                {"min_qty": 1, "max_qty": 5, "discount_percent": 0},
                {"min_qty": 6, "max_qty": 24, "discount_percent": 5},
                {"min_qty": 25, "max_qty": 99, "discount_percent": 10},
                {"min_qty": 100, "max_qty": None, "discount_percent": 15},
            ],
        },
    ),
    "digital_print": _make_category(
        pricing_method="per_sqft", base_rate=9.50, minimum_charge=40.00,
        markup=2.30, target_margin=40.0, waste_percent=10.0,
        default_material="print_adhesive_vinyl",
        extras={
            "file_prep_fee": 20.00,
            # EC9 Phase 9E-1 additions (EC09 controlling document, Digital Print section)
            "min_billable_area_sqft": 1.0,
            "base_ink_coverage_percent": 75.0,
            "ink_consumable_rate_per_sqft": 0.75,
            "quality_multipliers": {"draft": 0.90, "standard": 1.00, "high": 1.15, "photo": 1.30},
            "laminate_rate_per_sqft": 1.00,
            "mounting_labor_hr_per_sqft": 0.08,
            "piece_separation_labor_hr_each": 0.02,
            "production_labor_hr_per_sqft": 0.08,
            "production_labor_min_hours": 0.2,
            "design_default_hours": 0.5,
            "install_base_hr_per_sqft": 0.08,
            "quantity_tiers": [
                {"min_qty": 1, "max_qty": 4, "discount_percent": 0},
                {"min_qty": 5, "max_qty": 24, "discount_percent": 5},
                {"min_qty": 25, "max_qty": 99, "discount_percent": 10},
                {"min_qty": 100, "max_qty": None, "discount_percent": 15},
            ],
        },
    ),
    "vehicle_graphics": _make_category(
        pricing_method="cost_plus_labor", base_rate=None, minimum_charge=150.00,
        markup=2.40, target_margin=42.0, waste_percent=12.0,
        default_material="wrap_calendered",
        extras={
            "printed_wrap_sell_per_sqft": 19.00,
            "color_change_wrap_sell_per_sqft": 17.00,
            "install_included": True,
            "install_min_charge": 125.00,
        },
    ),
    "apparel": _make_category(
        pricing_method="per_sqft", base_rate=None, minimum_charge=60.00,
        markup=2.15, target_margin=38.0, waste_percent=0.0,
        default_material=None,
        extras={
            # Legacy MVP fields kept for backward compatibility with any
            # pre-Phase-9E-2 record that referenced them directly.
            "blank_tshirt_cost": 3.25,
            "decoration_cost_per_garment": 0.50,
            "production_minutes_per_garment": 2.0,
            "basic_setup_fee": 10.00,
            # EC9 Phase 9E-2 — EC09 controlling document, Apparel section.
            "garments": APPAREL_GARMENTS,
            "decoration_methods": APPAREL_DECORATION_METHODS,
            "default_decoration_method": "htv",
            "design_default_hours": 0.5,
            "design_setup_fee_by_complexity": {"simple": 10.00, "medium": 15.00, "complex": 25.00, "extreme": 30.00},
            "plus_size_upcharge": 2.00,
            "custom_name_number_charge_garment": 4.00,
            "custom_name_number_charge_hat": 3.00,
            "specialty_finish_charge_garment": 2.00,
            "specialty_finish_charge_hat": 1.50,
            "two_tone_hat_finish_charge": 1.50,
            "leather_patch_charge": 2.50,
            "bag_and_fold_charge": 1.00,
            "rush_default_percent": 17.5,
            "decoration_area_sqin_by_placement": {"front": 16, "back": 100, "combo": 116, "hat": 9},
            "quantity_tiers": [
                {"min_qty": 1,  "discount_percent": 0},
                {"min_qty": 12, "discount_percent": 5},
                {"min_qty": 25, "discount_percent": 10},
                {"min_qty": 100,"discount_percent": 15},
            ],
        },
    ),
    "services": _make_category(
        pricing_method="cost_plus_labor", base_rate=None, minimum_charge=25.00,
        markup=1.80, target_margin=35.0, waste_percent=0.0,
        default_material=None,
        extras={
            "minimum_design_charge": 75.00,
            "minimum_install_charge": 150.00,
            "trip_charge_default": 45.00,
            "mileage_rate_cost": 0.67,
            "mileage_rate_sell": 1.25,
        },
    ),
    "promotional": _make_category(
        pricing_method="cost_plus_labor", base_rate=None, minimum_charge=50.00,
        markup=1.50, target_margin=33.0, waste_percent=0.0, needs_tenant_setup=True,
        extras={
            "minimum_setup_fee": 25.00,
            # EC9 Phase 9E-2 — EC09 controlling document, Promotional Items
            # section "Foundation Values". This category is driven primarily
            # by the tenant's own PricingSavedItem library (business cards,
            # pens, mugs, vendor-supplied/custom-sourced items, etc.) — these
            # are just the toggle defaults for a brand-new one-time item.
            "default_setup_required": False,
            "default_decoration_fee_required": False,
            "default_personalization_required": False,
            "default_shipping_required": False,
            "default_rush": False,
            "default_known_supplier_cost": True,
        },
    ),
    "custom": _make_category(
        pricing_method="cost_plus_labor", base_rate=None, minimum_charge=50.00,
        markup=2.25, target_margin=38.0, waste_percent=0.0,
        extras={"labor_hours_per_unit_default": 0.25},
    ),
}


def build_starter_pack() -> dict[str, Any]:
    """Return a fresh copy of the starter default pack. Never returns the same dict twice."""
    import copy
    return {
        "starter_default_version": STARTER_DEFAULT_VERSION,
        "shop_defaults": dict(SHOP_DEFAULTS),
        "materials": copy.deepcopy(MATERIALS),
        "category_defaults": copy.deepcopy(CATEGORY_DEFAULTS),
        "category_meta": copy.deepcopy(CATEGORY_META),
        "setup_quiz_metadata": {
            "last_setup_quiz_completed_at": None,
            "categories_completed": [],
        },
    }

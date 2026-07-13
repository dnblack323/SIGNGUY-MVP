"""EC9 Phase 9C — Grouped Pricing Setup Quiz.

One grouped, representative-job scenario (a handful of practical questions)
derives PROVISIONAL Pricing Foundation suggestions. This is additive to, and
reuses, the existing shop-level pricing settings and `calculate_pricing()`
pipeline (`services/pricing.py`) — no second pricing/settings system.

No live AI calls, no market research, no historical invoice analysis, and no
category-specific calculator formulas are involved here (those are Phase
9E/9G). Every derived number is computed with plain, shown arithmetic from
the owner's own answers plus the tenant's CURRENT shop-level Pricing
Foundation settings (overhead %, target margin %) as anchors.
"""
from __future__ import annotations

from typing import Any, Optional

from ..core.db import db
from ..core.time_utils import utc_now
from ..models.pricing_quiz_submission import PricingQuizSubmission
from .pricing import get_or_init_pricing_settings, update_shop_defaults
from .starter_defaults import CATEGORY_IDS

DIFFICULTY_MULTIPLIERS: dict[str, float] = {"easy": 0.9, "typical": 1.0, "difficult": 1.25, "rush": 1.5}

REQUIRED_ANSWER_FIELDS = [
    "category", "job_duration_hours", "crew_size", "customer_charge", "price_floor",
]


def _now_iso() -> str:
    return utc_now().isoformat()


def derive_quiz_suggestions(answers: dict[str, Any], shop_defaults: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Pure function: representative-job answers -> provisional suggestions + shown math."""
    category = answers["category"]
    duration_hours = float(answers["job_duration_hours"])
    crew_size = int(answers["crew_size"])
    material_cost = float(answers.get("material_cost_estimate") or 0)
    customer_charge = float(answers["customer_charge"])
    price_floor = float(answers["price_floor"])
    difficulty = answers.get("difficulty") or "typical"
    math: list[str] = []

    total_person_hours = duration_hours * crew_size
    math.append(f"Total person-hours = {duration_hours:g} hrs x {crew_size} people = {total_person_hours:.2f} person-hrs")

    mult = DIFFICULTY_MULTIPLIERS.get(difficulty, 1.0)
    baseline_charge = (customer_charge / mult) if mult else customer_charge
    math.append(f"Baseline charge (normalizing a '{difficulty}' job, x{mult:g}) = ${customer_charge:.2f} / {mult:g} = ${baseline_charge:.2f}")

    design_allowance = round(baseline_charge * 0.15, 2) if answers.get("includes_design") else 0.0
    install_allowance = round(baseline_charge * 0.20, 2) if answers.get("includes_install") else 0.0
    setup_allowance = 0.0
    if answers.get("includes_setup"):
        setup_allowance += baseline_charge * 0.05
    if answers.get("includes_finishing"):
        setup_allowance += baseline_charge * 0.05
    setup_allowance = round(setup_allowance, 2)
    if design_allowance:
        math.append(f"Design allowance = 15% of baseline = ${design_allowance:.2f}")
    if install_allowance:
        math.append(f"Install allowance = 20% of baseline = ${install_allowance:.2f}")
    if setup_allowance:
        math.append(f"Setup/finishing allowance = 5% (+5% if both) of baseline = ${setup_allowance:.2f}")

    remaining = round(baseline_charge - design_allowance - install_allowance - setup_allowance, 2)
    math.append(f"Remaining for material + labor = ${baseline_charge:.2f} - allowances = ${remaining:.2f}")

    material_component = round(min(material_cost, max(remaining, 0.0)), 2)
    labor_dollars = round(max(remaining - material_component, 0.0), 2)
    math.append(f"Material component (capped at remaining) = ${material_component:.2f}; Labor dollars = ${remaining:.2f} - ${material_component:.2f} = ${labor_dollars:.2f}")

    labor_rate = round(labor_dollars / total_person_hours, 2) if total_person_hours > 0 else None
    if labor_rate is not None:
        math.append(f"Suggested labor rate = ${labor_dollars:.2f} / {total_person_hours:.2f} person-hrs = ${labor_rate:.2f}/hr")

    effective_shop_rate = round(customer_charge / total_person_hours, 2) if total_person_hours > 0 else None
    if effective_shop_rate is not None:
        math.append(f"Effective shop rate (actual $/person-hr charged) = ${customer_charge:.2f} / {total_person_hours:.2f} person-hrs = ${effective_shop_rate:.2f}/hr")

    overhead_percent = float(shop_defaults.get("default_overhead_percent") or 0)
    overhead_recovery = round(baseline_charge * (overhead_percent / 100), 2)
    math.append(f"Overhead recovery = current shop overhead {overhead_percent:.1f}% of baseline = ${overhead_recovery:.2f}")

    target_margin = float(shop_defaults.get("target_profit_margin_percent") or 0)
    suggested_sell_rate: Optional[float] = None
    if labor_rate is not None:
        if target_margin < 100:
            suggested_sell_rate = round(labor_rate / (1 - target_margin / 100), 2)
            math.append(f"Suggested go-forward sell rate = labor rate / (1 - current target margin {target_margin:.1f}%) = ${labor_rate:.2f} / {1 - target_margin/100:.2f} = ${suggested_sell_rate:.2f}/hr")
        else:
            markup = float(shop_defaults.get("default_markup_multiplier") or 1)
            suggested_sell_rate = round(labor_rate * markup, 2)
            math.append(f"Suggested go-forward sell rate = labor rate x current markup multiplier {markup:g} = ${suggested_sell_rate:.2f}/hr")

    minimum_charge = round(price_floor, 2)
    math.append(f"Minimum charge = the lowest price you said you'd accept = ${minimum_charge:.2f}")

    suggested_shop_defaults_map: dict[str, float] = {}
    if labor_rate is not None:
        suggested_shop_defaults_map["production_hourly_rate"] = labor_rate
    if minimum_charge is not None:
        suggested_shop_defaults_map["minimum_order_amount"] = minimum_charge
    suggested_shop_defaults_map["target_profit_margin_percent"] = target_margin

    suggestions = {
        "labor_rate": labor_rate,
        "effective_shop_rate": effective_shop_rate,
        "minimum_charge": minimum_charge,
        "overhead_recovery": overhead_recovery,
        "target_margin": target_margin,
        "suggested_sell_rate": suggested_sell_rate,
        "design_allowance": design_allowance or None,
        "install_allowance": install_allowance or None,
        "setup_allowance": setup_allowance or None,
        "category_assumptions": {
            "category": category,
            "difficulty": difficulty,
            "total_person_hours": round(total_person_hours, 2),
        },
        # A reasonable, clearly-labeled starting point for "accept all" in the
        # frontend review step. The owner may still edit/reject any entry —
        # this map is NOT applied automatically; `apply_quiz_suggestions`
        # only ever writes whatever the caller explicitly submits.
        "suggested_shop_defaults_map": suggested_shop_defaults_map,
    }
    return suggestions, math


async def submit_quiz(tenant_id: str, answers: dict[str, Any]) -> dict[str, Any]:
    missing = [f for f in REQUIRED_ANSWER_FIELDS if answers.get(f) in (None, "")]
    if missing:
        raise ValueError(f"Missing required answer(s): {missing}")
    if answers.get("category") not in CATEGORY_IDS:
        raise ValueError(f"Unknown category: {answers.get('category')}")
    settings = await get_or_init_pricing_settings(tenant_id)
    suggestions, math_shown = derive_quiz_suggestions(answers, settings.get("shop_defaults") or {})
    doc = PricingQuizSubmission(
        tenant_id=tenant_id, category=answers["category"], answers=answers,
        derived_suggestions=suggestions, math_shown=math_shown, status="draft",
    ).model_dump()
    await db.pricing_quiz_submissions.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


async def list_submissions(tenant_id: str, status: Optional[str] = None) -> list[dict[str, Any]]:
    filt: dict[str, Any] = {"tenant_id": tenant_id}
    if status:
        filt["status"] = status
    return [d async for d in db.pricing_quiz_submissions.find(filt, {"_id": 0}).sort("created_at", -1)]


async def get_submission(tenant_id: str, submission_id: str) -> Optional[dict[str, Any]]:
    return await db.pricing_quiz_submissions.find_one({"tenant_id": tenant_id, "id": submission_id}, {"_id": 0})


async def apply_quiz_suggestions(tenant_id: str, submission_id: str, accepted_shop_defaults: dict[str, float], actor_user_id: Optional[str] = None) -> dict[str, Any]:
    """Apply ONLY the fields explicitly present in `accepted_shop_defaults` —
    never the raw suggestion set. Owner-rejected/edited fields are respected
    because the caller (after review) decides exactly what's in this dict."""
    submission = await get_submission(tenant_id, submission_id)
    if not submission:
        raise ValueError("Quiz submission not found")
    if not accepted_shop_defaults:
        raise ValueError("No fields accepted to apply")
    await update_shop_defaults(tenant_id, accepted_shop_defaults, source="grouped_quiz")
    updates = {
        "status": "applied",
        "applied_fields": accepted_shop_defaults,
        "applied_at": _now_iso(),
        "applied_by_user_id": actor_user_id,
        "updated_at": _now_iso(),
    }
    await db.pricing_quiz_submissions.update_one({"tenant_id": tenant_id, "id": submission_id}, {"$set": updates})
    return await get_submission(tenant_id, submission_id) or {}


async def skip_submission(tenant_id: str, submission_id: str) -> dict[str, Any]:
    res = await db.pricing_quiz_submissions.update_one(
        {"tenant_id": tenant_id, "id": submission_id},
        {"$set": {"status": "skipped", "updated_at": _now_iso()}},
    )
    if res.matched_count == 0:
        raise ValueError("Quiz submission not found")
    return await get_submission(tenant_id, submission_id) or {}

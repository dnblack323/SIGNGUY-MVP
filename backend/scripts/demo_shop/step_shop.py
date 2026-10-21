"""Shop foundation: platform content, profile, customers, team, materials/equipment, pricing foundation."""
from __future__ import annotations

import secrets

from scripts.demo_shop import data, data_shop


async def ensure(ctx, kind: str, existing: dict, name: str, create) -> dict:
    """Return the existing record for ``name`` or create it; counts either outcome for the run summary."""
    row = existing.get(name)
    if row is None:
        row = await create()
        existing[name] = row
        ctx.note(kind, True)
    else:
        ctx.note(kind, False)
    return row


async def platform(ctx) -> None:
    """Platform-level system content (help, onboarding program, local AI/assistant catalogs). No provider calls."""
    for path in ("/onboarding/platform/bootstrap", "/ai-studio/platform/bootstrap", "/assistant/platform/bootstrap"):
        await ctx.api.post(path)
    await ctx.api.post("/templates/packs/starter/install")


async def shop_profile(ctx) -> None:
    await ctx.api.post("/onboarding/company-profile/apply", {"company_profile": data_shop.COMPANY_PROFILE, "branding": data_shop.BRANDING})


async def customers(ctx) -> None:
    existing = {c["name"]: c for c in await ctx.api.items("/customers", limit=200, status="all")}
    for key, payload in data.CUSTOMERS.items():
        row = await ensure(ctx, "customers", existing, payload["name"], lambda p=payload: ctx.api.post("/customers", p))
        ctx.ids[f"customer:{key}"] = row["id"]


async def team(ctx) -> None:
    api = ctx.api
    users = {u["email"]: u for u in await api.items("/users")}
    employees = {e["email"]: e for e in await api.items("/employees", limit=200)}
    for key, name, email, role, cents, hired in data_shop.STAFF:
        user = await ensure(ctx, "staff_users", users, email, lambda n=name, e=email: api.post(
            "/users", {"email": e, "full_name": n, "role": "staff", "password": secrets.token_urlsafe(24)}))
        emp = await ensure(ctx, "employees", employees, email, lambda n=name, e=email, r=role, c=cents, h=hired, u=user: api.post(
            "/employees", {"name": n, "email": e, "role_label": r, "hourly_rate_cents": c, "hire_date": h, "linked_user_id": u["id"],
                           "notes": "Fictional demonstration employee."}))
        ctx.ids[f"user:{key}"], ctx.ids[f"employee:{key}"] = user["id"], emp["id"]
    ctx.ids["user:owner"] = api.user["id"]


async def resources(ctx) -> None:
    api = ctx.api
    vendors = {v["name"]: v for v in await api.items("/vendors")}
    for name, desc, cats, email, phone in data_shop.VENDORS:
        await ensure(ctx, "vendors", vendors, name, lambda n=name, d=desc, c=cats, e=email, p=phone: api.post(
            "/vendors", {"name": n, "categories": c, "contact_email": e, "contact_phone": p, "notes": d, "preferred": True}))
    locs = {loc["name"]: loc for loc in await api.items("/inventory/locations")}
    for name, kind in data_shop.LOCATIONS:
        await ensure(ctx, "inventory_locations", locs, name, lambda n=name, k=kind: api.post("/inventory/locations", {"name": n, "kind": k}))
    mats = {m["name"]: m for m in await api.items("/materials", limit=200)}
    for key, (name, sku, cat, unit, cost, extra, stock, reorder, reorder_qty) in data_shop.MATERIALS.items():
        fresh = name not in mats
        row = await ensure(ctx, "materials", mats, name, lambda **_: api.post("/materials", {
            "name": name, "sku": sku, "category": cat, "unit_of_measure": unit, "purchase_unit": unit, "current_cost_cents": cost,
            "cost_unit": unit, "reorder_point": reorder, "reorder_quantity": reorder_qty, "stock_tracked": True, **extra}))
        ctx.ids[f"material:{key}"] = row["id"]
        if fresh:
            for loc_name, qty in stock:
                await api.post("/inventory/adjustments/increase", {
                    "material_id": row["id"], "location_id": locs[loc_name]["id"], "quantity": qty,
                    "reason": "Opening stock (demonstration data)", "unit_of_measure": unit})
    equipment = {e["name"]: e for e in await api.items("/equipment")}
    for name, cat, make, model, serial, location, safety in data_shop.EQUIPMENT:
        row = await ensure(ctx, "equipment", equipment, name, lambda **_: api.post("/equipment", {
            "name": name, "category": cat, "manufacturer": make, "model": model, "serial_number": serial, "location": location,
            "status": "active", "safety_sensitive": safety, "description": f"{name} (demonstration equipment)."}))
        ctx.ids[f"equipment:{name}"] = row["id"]


async def pricing(ctx) -> None:
    """Material pricing profiles and reusable charges on the existing Pricing Foundation (no second pricing system)."""
    api = ctx.api
    for key, profile in data_shop.PRICING_PROFILES.items():
        material_id = ctx.ids[f"material:{key}"]
        existing = await api.items("/pricing/material-profiles")
        have = next((p for p in existing if p.get("material_id") == material_id), None)
        if have is None:
            have = await api.post(f"/pricing/material-profiles/materials/{material_id}", {**profile, "pricing_source": "manual",
                                  "pricing_notes": "Example pricing for the demonstration shop."})
            ctx.note("pricing_profiles", True)
        else:
            ctx.note("pricing_profiles", False)
        ctx.ids[f"profile:{key}"] = have["id"]
    components = {c["key"]: c for c in await api.items("/pricing/components")}
    for key, name, charge_type, amount, percent, cats in data_shop.PRICING_COMPONENTS:
        row = await ensure(ctx, "pricing_components", components, key, lambda **_: api.post("/pricing/components", {
            "key": key, "name": name, "charge_type": charge_type, "amount": amount or 0, "percent": percent or 0,
            "category_applicability": cats, "notes": "Example charge for the demonstration shop.", "active": True}))
        ctx.ids[f"component:{key}"] = row["id"]

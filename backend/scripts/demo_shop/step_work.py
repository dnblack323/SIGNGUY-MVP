"""Sales and production: quotes -> orders -> work orders -> production stages -> invoices -> payments.

Everything goes through the canonical routers (same validation, numbering, snapshots and activity
records as the UI). Re-running is safe: each phase checks what already exists before acting.
"""
from __future__ import annotations

from datetime import date, timedelta

from scripts.demo_shop import data_work as dw
from scripts.demo_shop.client import DemoSeedError

QUOTE_RANK = {"draft": 0, "sent": 1, "viewed": 2, "approved": 3}
ORDER_RANK = {"draft": 0, "confirmed": 1, "in_production": 2, "ready": 3, "completed": 4}
WO_RANK = {"draft": 0, "released": 1, "queued": 2, "in_progress": 3, "blocked": 3, "ready": 4, "completed": 5}


def day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def line_payload(it: dict, customer_key: str, discount_cents: int = 0) -> dict:
    gross = it["quantity"] * it["unit_price_cents"] - discount_cents
    tax = 0 if customer_key in dw.TAX_EXEMPT else round(gross * dw.TAX_RATE_BP / 10000)
    payload = {k: v for k, v in it.items() if v is not None}
    payload["discount_cents"], payload["tax_cents"] = discount_cents, tax
    return payload


async def _quote(ctx, quotes: dict, key: str, customer: str, job: str, items: list, final: str, expires_days: int, discount_cents: int = 0) -> dict:
    api = ctx.api
    quote = quotes.get(job)
    if quote is None:
        quote = await api.post("/quotes", {
            "customer_id": ctx.ids[f"customer:{customer}"], "job_name": job, "expires_at": day(expires_days),
            "notes_customer": "Demonstration quote. Prices are examples.", "notes_internal": "Seeded demonstration data."})
        for n, it in enumerate(items):
            await api.post(f"/quotes/{quote['id']}/line-items", line_payload(it, customer, discount_cents if n == 0 else 0))
        quotes[job] = quote
        ctx.note("quotes", True)
    else:
        ctx.note("quotes", False)
    current = (await api.get(f"/quotes/{quote['id']}"))
    current = current.get("quote", current)
    status = current["status"]
    if final == "declined":
        if status in ("draft", "sent"):
            if status == "draft":
                await api.post(f"/quotes/{quote['id']}/status", {"status": "sent"})
            await api.post(f"/quotes/{quote['id']}/status", {"status": "declined", "reason": "Customer chose a different vendor (demonstration)"})
    elif status in QUOTE_RANK and QUOTE_RANK[status] < QUOTE_RANK[final]:
        for step in ("sent", "viewed", "approved"):
            if QUOTE_RANK[step] > QUOTE_RANK[status] and QUOTE_RANK[step] <= QUOTE_RANK[final]:
                await api.post(f"/quotes/{quote['id']}/status", {"status": step})
    ctx.ids[f"quote:{key}"] = quote["id"]
    return quote


async def _order(ctx, orders: dict, quote: dict, sc: dict) -> dict:
    api = ctx.api
    order = orders.get(sc["job"])
    if order is None:
        order = (await api.post(f"/quotes/{quote['id']}/convert-to-order", {}))["order"]
        orders[sc["job"]] = order
        await api.patch(f"/orders/{order['id']}", {"due_date": day(sc["due"]),
                        "notes_internal": "Seeded demonstration order.", "notes_customer": "Thank you for your business."})
        ctx.note("orders", True)
    else:
        ctx.note("orders", False)
    ctx.ids[f"order:{sc['key']}"] = order["id"]
    return order


async def _order_status(ctx, order_id: str, target: str) -> None:
    api = ctx.api
    current = (await api.get(f"/orders/{order_id}"))
    current = current.get("order", current)["status"]
    for step in ("confirmed", "in_production", "ready", "completed"):
        if ORDER_RANK[step] > ORDER_RANK[current] and ORDER_RANK[step] <= ORDER_RANK[target]:
            await api.post(f"/orders/{order_id}/status", {"status": step})
            current = step


async def _stages(ctx, wo_id: str, plan: dict) -> None:
    api = ctx.api
    rows = (await api.get(f"/work-orders/{wo_id}/stages"))["stages"]
    if not rows:
        rows = (await api.post(f"/work-orders/{wo_id}/stages/generate")).get("stages", [])
        rows = (await api.get(f"/work-orders/{wo_id}/stages"))["stages"]
    by_instance: dict[str, list] = {}
    for row in sorted(rows, key=lambda r: r["sequence"]):
        by_instance.setdefault(row["workflow_instance_id"], []).append(row)
    for group in by_instance.values():
        if any(s["status"] != "not_started" for s in group):
            continue  # already progressed on a previous run
        done = len(group) if plan["stages_done"] == "all" else min(plan["stages_done"], len(group))
        for s in group[:done]:
            await _assign(ctx, s)
            await api.post(f"/production-stages/{s['id']}/start", {})
            await api.post(f"/production-stages/{s['id']}/complete", {"completion_note": "Completed (demonstration)."})
        state = plan["state"]
        if state and done < len(group):
            s = group[done]
            await _assign(ctx, s)
            if state == "start":
                await api.post(f"/production-stages/{s['id']}/start", {})
            else:
                action, reason = state
                await api.post(f"/production-stages/{s['id']}/start", {})
                await api.post(f"/production-stages/{s['id']}/{action}", {"reason": reason})


async def _assign(ctx, stage: dict) -> None:
    owner = dw.STAGE_OWNER.get(stage["stage_key"], "carla")
    await ctx.api.post(f"/production-stages/{stage['id']}/assign", {"employee_id": ctx.ids[f"employee:{owner}"], "override_reason": "Demonstration assignment"})


async def _work_order(ctx, sc: dict, order: dict) -> None:
    api = ctx.api
    plan = sc["wo"]
    existing = [w for w in await api.items("/work-orders", order_id=order["id"], limit=50) if w.get("order_id") == order["id"]]
    if existing:
        wo = existing[0]
        ctx.note("work_orders", False)
    else:
        wo = await api.post("/work-orders", {
            "order_id": order["id"], "priority": plan["priority"], "due_date": day(sc["due"]),
            "assigned_user_ids": [ctx.ids[f"user:{k}"] for k in plan["assign"]],
            "production_instructions": "Seeded demonstration work order."})
        ctx.note("work_orders", True)
    ctx.ids[f"wo:{sc['key']}"] = wo["id"]
    status = wo["production_status"]
    if WO_RANK.get(status, 0) < WO_RANK[plan["path"][-1]] or (plan["path"][-1] == "blocked" and status != "blocked"):
        for target in plan["path"]:
            if WO_RANK[target] > WO_RANK.get(status, 0) or (target == "blocked" and status != "blocked"):
                body = {"target": target}
                if target == "blocked":
                    body["reason"] = plan["state"][1] if isinstance(plan["state"], tuple) else "On hold"
                await api.post(f"/work-orders/{wo['id']}/transition", body)
                status = target
                if target == "released":
                    await api.post(f"/work-orders/{wo['id']}/stages/generate")
    await _stages(ctx, wo["id"], plan)


async def _invoice(ctx, sc: dict, order: dict) -> None:
    api = ctx.api
    spec = sc["invoice"]
    full = (await api.get(f"/orders/{order['id']}"))
    total = full.get("order", full)["total_cents"]
    existing = [i for i in await api.items("/invoices", order_id=order["id"], limit=20) if i.get("order_id") == order["id"]]
    if existing:
        inv = existing[0]
        ctx.note("invoices", False)
    else:
        inv = (await api.post("/invoices", {"order_id": order["id"], "title": f"Invoice - {sc['job']}", "total_cents": total,
                                            "due_date": day(spec["due"]), "notes": "Demonstration invoice."}))["invoice"]
        ctx.note("invoices", True)
    ctx.ids[f"invoice:{sc['key']}"] = inv["id"]
    if spec["kind"] == "issued" and inv.get("document_status") == "draft":
        await api.post(f"/invoices/{inv['id']}/status", {"document_status": "issued"})
    if spec["kind"] != "issued" or sc["payments"] == [] or inv.get("amount_paid_cents"):
        return
    paid = 0
    for amount, method, ago, ref in sc["payments"]:
        cents = total - paid if amount is None else (round(total * amount) if isinstance(amount, float) else amount)
        await api.post(f"/invoices/{inv['id']}/payments", {
            "amount_cents": cents, "method": method, "paid_on": day(-ago), "reference": ref, "notes": "Fictional payment record (no processor used)."})
        paid += cents
        ctx.note("payments", True)


async def sales(ctx) -> None:
    api = ctx.api
    await api.get("/production-workflows")  # seeds the starter workflows the stage generator resolves against
    quotes = {q["job_name"]: q for q in await api.items("/quotes", limit=200)}
    orders = {o["job_name"]: o for o in await api.items("/orders", limit=200)}
    for sc in dw.SCENARIOS:
        quote = await _quote(ctx, quotes, sc["key"], sc["customer"], sc["job"], sc["items"], "approved", 30, sc.get("discount_cents", 0))
        order = await _order(ctx, orders, quote, sc)
        await _order_status(ctx, order["id"], "confirmed")
        await _work_order(ctx, sc, order)
        await _order_status(ctx, order["id"], sc["order"])
        await _invoice(ctx, sc, order)
    for key, customer, job, final, items, expires in dw.OPEN_QUOTES:
        await _quote(ctx, quotes, key, customer, job, items, final, expires)

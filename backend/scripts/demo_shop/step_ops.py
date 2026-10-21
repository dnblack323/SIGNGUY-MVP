"""Operations: expenses, shop schedule, calendar events, tasks, announcements and time records."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from scripts.demo_shop import data_ops as do
from scripts.demo_shop.step_shop import ensure
from scripts.demo_shop.step_work import day

try:  # shop-local wall-clock times -> offset-aware ISO strings
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - tz database unavailable
    _TZ = None


def at(offset_days: int, hour: float) -> str:
    base = datetime.combine(date.today() + timedelta(days=offset_days), time(0)) + timedelta(hours=hour)
    if _TZ is not None:
        return base.replace(tzinfo=_TZ).isoformat()
    return base.isoformat() + "-04:00"


async def expenses(ctx) -> None:
    api = ctx.api
    existing = {e["description"]: e for e in await api.items("/expenses", limit=200)}
    vendors = {v["name"]: v for v in await api.items("/vendors")}
    for ago, category, desc, cents, tax, method, vendor, order_key, recurring in do.EXPENSES:
        body = {"expense_date": day(-ago), "category_key": category, "description": desc, "amount_cents": cents, "tax_cents": tax,
                "payment_method": method, "recurring": recurring, "internal_notes": "Fictional demonstration expense."}
        if vendor:
            body["vendor_id"] = vendors[vendor]["id"]
        if order_key:
            body["order_id"] = ctx.ids[f"order:{order_key}"]
        await ensure(ctx, "expenses", existing, desc, lambda b=body: api.post("/expenses", b))


async def schedule(ctx) -> None:
    """Publish this week's and next week's shop schedules with a shift per employee per working day."""
    api = ctx.api
    for week_offset in (0, 7):
        sched = await api.get("/schedules", period_start=day(week_offset))
        header, shifts = sched["schedule"], sched["shifts"]
        have = {(s["employee_id"], s["shift_date"]) for s in shifts if s.get("status") != "canceled"}
        start = date.fromisoformat(header["period_start"])
        for n in range(7):
            d = start + timedelta(days=n)
            if d.weekday() >= 5:  # Sat/Sun off
                continue
            for key, (title, location) in do.SHIFT_TEMPLATE.items():
                emp_id = ctx.ids[f"employee:{key}"]
                if (emp_id, d.isoformat()) in have:
                    ctx.note("shifts", False)
                    continue
                hour_in, hour_out = {"devon": (7.5, 16.0), "aisha": (9.0, 17.5), "tomas": (7.0, 15.5)}.get(key, (8.0, 16.5))
                await api.post(f"/schedules/{header['id']}/shifts", {
                    "employee_id": emp_id, "shift_date": d.isoformat(), "title": title, "location": location,
                    "start_at": at((d - date.today()).days, hour_in), "end_at": at((d - date.today()).days, hour_out),
                    "break_minutes_expected": 30})
                ctx.note("shifts", True)
        if header["status"] != "published":
            await api.post(f"/schedules/{header['id']}/publish")


async def calendar(ctx) -> None:
    api = ctx.api
    found = await _calendar_titles(ctx)
    for days_out, hour, hours, etype, title, customer, order_key, staff, location in do.CALENDAR:
        start_iso = at(days_out, hour)
        if (title, start_iso[:10]) in found:
            ctx.note("calendar_events", False)
            continue
        body = {"event_type": etype, "title": title, "start_at": start_iso, "end_at": at(days_out, hour + hours), "location": location,
                "assigned_employee_ids": [ctx.ids[f"employee:{k}"] for k in staff], "visibility": "staff",
                "description": "Seeded demonstration event.",
                "conflict_override_reason": "Work assigned inside the regular shift (demonstration)"}
        if customer:
            body["customer_id"] = ctx.ids[f"customer:{customer}"]
        if order_key:
            body["order_id"] = ctx.ids[f"order:{order_key}"]
            body["work_order_id"] = ctx.ids[f"wo:{order_key}"]
        await api.post("/calendar/events", body)
        ctx.note("calendar_events", True)


async def calendar_rows(ctx) -> list[dict]:
    feed = await ctx.api.get("/calendar/feed", start_at=at(-30, 0), end_at=at(60, 0))
    return feed.get("events") or feed.get("items") or []


async def _calendar_titles(ctx) -> set:
    return {(r["title"], r["start_at"][:10]) for r in await calendar_rows(ctx)}


async def tasks(ctx) -> None:
    api = ctx.api
    existing = {t["title"]: t for t in await api.items("/tasks", limit=200)}
    for title, desc, priority, order_key, customer, assignee, due, action in do.TASKS:
        body = {"title": title, "description": desc, "priority": priority, "assigned_employee_id": ctx.ids[f"employee:{assignee}"],
                "due_at": at(due, 17)}
        if order_key:
            body["order_id"], body["work_order_id"] = ctx.ids[f"order:{order_key}"], ctx.ids[f"wo:{order_key}"]
        if customer:
            body["customer_id"] = ctx.ids[f"customer:{customer}"]
        fresh = title not in existing
        task = await ensure(ctx, "tasks", existing, title, lambda b=body: api.post("/tasks", b))
        if fresh and action:
            if action in ("wait", "block", "complete"):
                await api.post(f"/tasks/{task['id']}/start", {})
            reason = {"wait": "Waiting on customer", "block": "Blocked by landlord permit", "complete": "Done"}.get(action)
            await api.post(f"/tasks/{task['id']}/{action}", {"reason": reason} if reason else {})


async def announcements(ctx) -> None:
    api = ctx.api
    existing = {a["title"]: a for a in await api.items("/announcements")}
    title, body = do.ANNOUNCEMENT
    fresh = title not in existing
    row = await ensure(ctx, "announcements", existing, title, lambda: api.post("/announcements", {"title": title, "body": body, "audience": "all"}))
    if fresh:
        await api.post(f"/announcements/{row['id']}/publish")


async def time_records(ctx) -> None:
    """Closed time-clock entries for the last three working days (clock in/out, then corrected to the shop's real hours)."""
    api = ctx.api
    entries = await api.items("/time-clock/entries/all", limit=500)
    have = {(e["employee_id"], (e.get("clock_in_at") or "")[:10]) for e in entries}
    for key, ago, start_h, end_h, _brk in do.TIME_ENTRIES:
        emp_id = ctx.ids[f"employee:{key}"]
        when = at(-ago, start_h)
        if (emp_id, when[:10]) in have:
            ctx.note("time_entries", False)
            continue
        await api.post(f"/time-clock/{emp_id}/clock-in", {"notes": "Demonstration time record"})
        await api.post(f"/time-clock/{emp_id}/clock-out")
        latest = max((await api.items("/time-clock/entries/all", employee_id=emp_id, limit=50)), key=lambda e: e["created_at"])
        await api.post(f"/time-clock/entries/{latest['id']}/correct", {
            "clock_in_at": when, "clock_out_at": at(-ago, end_h), "reason": "Seeded demonstration hours", "notes": "Demonstration time record"})
        ctx.note("time_entries", True)

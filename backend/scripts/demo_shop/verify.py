"""Read-only verification that the demo shop is complete and internally coherent.

Checks structure (one tenant, no obsolete collections), relationships (no orphans, every reference resolves,
every file exists in storage), money (order/invoice/payment totals reconcile) and that the main screens' APIs load.
Exits non-zero if any check fails. Writes nothing (the only side effect is the demo owner's usual dev-login stamp).
"""
from __future__ import annotations

from scripts.demo_shop.client import DemoApi

MIN_COUNTS = {"customers": 15, "orders": 15, "work_orders": 15, "employees": 4, "webstores": 4, "wrap_projects": 4, "invoices": 12,
              "payments": 8, "materials": 15, "equipment": 4, "expenses": 10, "tasks": 8, "calendar_events": 8, "shifts": 20, "production_stage_instances": 40, "time_entries": 8}
RETIRED_COLLECTIONS = {"webstore_questionnaire_templates"}


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.rows.append((name, bool(ok), detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)

    @property
    def failed(self) -> int:
        return sum(1 for _n, ok, _d in self.rows if not ok)


async def _ids(db, collection: str, **flt) -> set:
    return {d["id"] async for d in db[collection].find(flt, {"_id": 0, "id": 1})}


async def _refs(r: Report, db, name: str, collection: str, field: str, target: set, **flt) -> None:
    bad = [d async for d in db[collection].find({**flt, field: {"$nin": [None, ""]}}, {"_id": 0, "id": 1, field: 1}) if d[field] not in target]
    r.check(f"{name}: every {field} resolves", not bad, f"{len(bad)} dangling" if bad else "")


async def run(api: DemoApi) -> int:
    from app.core.db import db
    from app.services import storage

    r = Report()
    tenant = api.tenant
    tid = tenant["id"]
    print("structure")
    r.check("exactly one tenant", await db.tenants.count_documents({}) == 1)
    r.check("tenant is SIGNGUY DEMO SHOP", tenant.get("name") == "SIGNGUY DEMO SHOP", tenant.get("name", ""))
    r.check("no retired questionnaire collection", not (RETIRED_COLLECTIONS & set(await db.list_collection_names())))
    r.check("dev login returned a platform-capable owner", bool(api.user.get("email")))
    for coll, minimum in MIN_COUNTS.items():
        n = await db[coll].count_documents({})
        r.check(f"{coll} >= {minimum}", n >= minimum, str(n))
    stray = [c for c in ("customers", "orders", "invoices", "work_orders", "webstores", "employees") if await db[c].count_documents({"tenant_id": {"$ne": tid}})]
    r.check("no records belong to another tenant", not stray, ", ".join(stray))

    print("relationships")
    customers, orders = await _ids(db, "customers"), await _ids(db, "orders")
    items, wos, invoices = await _ids(db, "order_items"), await _ids(db, "work_orders"), await _ids(db, "invoices")
    employees, users, files = await _ids(db, "employees"), await _ids(db, "users"), await _ids(db, "files")
    await _refs(r, db, "orders", "orders", "customer_id", customers)
    await _refs(r, db, "quotes", "quotes", "customer_id", customers)
    await _refs(r, db, "order items", "order_items", "order_id", orders)
    await _refs(r, db, "work orders", "work_orders", "order_id", orders)
    await _refs(r, db, "work orders", "work_orders", "customer_id", customers)
    await _refs(r, db, "production stages", "production_stage_instances", "work_order_id", wos)
    await _refs(r, db, "production stages", "production_stage_instances", "order_item_id", items)
    await _refs(r, db, "invoices", "invoices", "order_id", orders)
    await _refs(r, db, "payments", "payments", "invoice_id", invoices)
    await _refs(r, db, "calendar events", "calendar_events", "customer_id", customers)
    await _refs(r, db, "calendar events", "calendar_events", "order_id", orders)
    await _refs(r, db, "calendar events", "calendar_events", "work_order_id", wos)
    await _refs(r, db, "tasks", "tasks", "order_id", orders)
    await _refs(r, db, "tasks", "tasks", "assigned_employee_id", employees)
    await _refs(r, db, "wrap projects", "wrap_projects", "customer_id", customers)
    await _refs(r, db, "wrap projects", "wrap_projects", "order_id", orders)
    await _refs(r, db, "wrap projects", "wrap_projects", "work_order_id", wos)
    await _refs(r, db, "wrap projects", "wrap_projects", "vehicle_id", await _ids(db, "wrap_vehicles"))
    await _refs(r, db, "schedule shifts", "shifts", "employee_id", employees)
    await _refs(r, db, "time entries", "time_entries", "employee_id", employees)
    await _refs(r, db, "employees", "employees", "linked_user_id", users)
    await _refs(r, db, "attachments", "attachments", "file_id", files)
    owners = await _ids(db, "webstore_owners")
    await _refs(r, db, "webstores", "webstores", "owner_id", owners)
    missing = []
    async for f in db.files.find({}, {"_id": 0, "id": 1, "storage_key": 1}):
        try:
            storage.get_bytes(f["storage_key"])
        except Exception:
            missing.append(f["id"])
    r.check("every file resolves in storage", not missing, f"{len(missing)} missing of {len(files)}" if missing else f"{len(files)} files")

    print("money")
    bad_orders = []
    async for o in db.orders.find({}, {"_id": 0, "id": 1, "number": 1, "total_cents": 1}):
        line_total = sum([i["line_total_cents"] async for i in db.order_items.find({"order_id": o["id"]}, {"_id": 0, "line_total_cents": 1})])
        if line_total != o["total_cents"] and abs(line_total - o["total_cents"]) > 0:
            bad_orders.append((o["number"], line_total, o["total_cents"]))
    r.check("order totals equal the sum of their items", not bad_orders, str(bad_orders[:3]))
    bad_inv = []
    async for inv in db.invoices.find({}, {"_id": 0}):
        paid = sum([p["amount_cents"] async for p in db.payments.find({"invoice_id": inv["id"], "status": {"$nin": ["voided", "void", "failed"]}}, {"_id": 0, "amount_cents": 1})])
        if inv["amount_paid_cents"] != paid or inv["balance_due_cents"] != inv["total_cents"] - paid:
            bad_inv.append((inv["number"], inv["total_cents"], inv["amount_paid_cents"], inv["balance_due_cents"], paid))
        order = await db.orders.find_one({"id": inv["order_id"]}, {"_id": 0, "total_cents": 1})
        if order and inv["total_cents"] != order["total_cents"]:
            bad_inv.append((inv["number"], "invoice total != order total", inv["total_cents"], order["total_cents"]))
    r.check("invoices reconcile (total - paid = balance; total = order total)", not bad_inv, str(bad_inv[:3]))
    deposit = await db.invoices.find_one({"amount_paid_cents": {"$gt": 0}, "balance_due_cents": {"$gt": 0}}, {"_id": 0, "number": 1})
    r.check("at least one partially paid invoice", deposit is not None)
    r.check("at least one fully paid invoice", await db.invoices.count_documents({"balance_due_cents": 0, "amount_paid_cents": {"$gt": 0}}) >= 1)
    r.check("at least one overdue unpaid invoice", await db.invoices.count_documents({"balance_due_cents": {"$gt": 0}, "due_date": {"$lt": __import__("datetime").date.today().isoformat()}, "document_status": "issued"}) >= 1)

    print("production")
    states = set(await db.work_orders.distinct("production_status"))
    r.check("work orders span several statuses", len(states) >= 4, ", ".join(sorted(states)))
    r.check("production stages exist and are assigned", await db.production_stage_instances.count_documents({"assigned_employee_id": {"$ne": None}}) > 10)
    r.check("a waiting stage and a blocked stage exist", await db.production_stage_instances.count_documents({"status": "waiting"}) >= 1 and await db.work_orders.count_documents({"production_status": "blocked"}) >= 1)

    print("screens (API loads)")
    paths = ["/customers", "/quotes", "/orders", "/work-orders", "/invoices", "/production/board", "/employees", "/tasks", "/webstores",
             "/wrap-lab/projects", "/wrap-lab/vehicles", "/materials", "/inventory/items", "/equipment", "/expenses", "/vendors", "/templates",
             "/forms/templates", "/pricing/settings", "/pricing/material-profiles", "/pricing/components", "/dashboard/summary", "/dashboard/home",
             "/announcements", "/time-clock/entries/all", "/finance/summary", "/finance/outstanding", "/documents"]
    for path in paths:
        try:
            await api.get(path)
            r.check(f"GET {path}", True)
        except Exception as exc:  # noqa: BLE001 - report every failing screen
            r.check(f"GET {path}", False, str(exc)[:140])
    for coll, route in (("orders", "/orders/{}"), ("customers", "/customers/{}"), ("work_orders", "/work-orders/{}"), ("invoices", "/invoices/{}"),
                        ("quotes", "/quotes/{}"), ("webstores", "/webstores/{}"), ("wrap_projects", "/wrap-lab/projects/{}")):
        failures = []
        async for d in db[coll].find({}, {"_id": 0, "id": 1}):
            try:
                await api.get(route.format(d["id"]))
            except Exception as exc:  # noqa: BLE001
                failures.append(str(exc)[:100])
        r.check(f"every {coll.replace('_', ' ')} record opens", not failures, failures[0] if failures else "")
    home = await api.get("/dashboard/home")
    populated = [k for k, w in home.get("data", {}).items() if w.get("state") == "ready" and (w.get("value") or w.get("total") or w.get("items") or w.get("rows"))]
    r.check("home widgets show data", len(populated) >= 5, f"{len(populated)} of {len(home.get('data', {}))}: " + ", ".join(populated))

    print("webstores")
    stores = await api.items("/webstores", limit=50)
    r.check("four webstores at different stages", len({s["status"] for s in stores}) >= 3, ", ".join(sorted({s["status"] for s in stores})))
    r.check("no store has checkout enabled", all(not s.get("checkout_enabled") for s in stores))
    r.check("no payment provider is connected", all(not s.get("stripe_payment_ready") for s in stores))
    r.check("questionnaires are Form Maker templates", await db.form_templates.count_documents({"module": "webstores"}) >= 7)
    print(f"\n{len(r.rows) - r.failed} passed, {r.failed} failed")
    return 1 if r.failed else 0

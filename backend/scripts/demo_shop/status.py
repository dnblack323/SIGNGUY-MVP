"""Read-only summary of what the demo shop currently contains."""
from __future__ import annotations

COLLECTIONS = ("tenants", "users", "customers", "quotes", "orders", "order_items", "work_orders", "invoices", "payments",
               "employees", "webstores", "wrap_projects", "materials", "equipment", "expenses", "files")


async def print_status() -> None:
    from app.core.db import db

    tenant = await db.tenants.find_one({"slug": "dev-shop"}, {"_id": 0, "id": 1, "name": 1})
    print("tenant:", tenant)
    for name in COLLECTIONS:
        print(f"  {name}: {await db[name].count_documents({})}")

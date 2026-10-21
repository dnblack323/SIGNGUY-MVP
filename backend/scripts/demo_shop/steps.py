"""Ordered, idempotent seed steps. Every record goes through the canonical API; none are inserted directly."""
from __future__ import annotations

from scripts.demo_shop import step_files, step_ops, step_shop, step_stores, step_wrap, step_work

ORDERED = [
    ("platform content", step_shop.platform),
    ("shop profile", step_shop.shop_profile),
    ("customers", step_shop.customers),
    ("team", step_shop.team),
    ("materials, vendors, equipment", step_shop.resources),
    ("pricing foundation", step_shop.pricing),
    ("quotes, orders, production, invoices, payments", step_work.sales),
    ("expenses", step_ops.expenses),
    ("schedule", step_ops.schedule),
    ("calendar", step_ops.calendar),
    ("tasks and announcements", step_ops.tasks),
    ("announcements", step_ops.announcements),
    ("time records", step_ops.time_records),
    ("artwork and files", step_files.artwork),
    ("wrap lab", step_wrap.wrap_lab),
    ("webstores", step_stores.webstores),
]

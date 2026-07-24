"""Create or remove tenant-scoped development sample data.

This script is intentionally local-development only. It creates fictional,
connected records that exercise the app without calling Stripe, email, SMS,
AI providers, or webhooks.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.db import db, ensure_indexes  # noqa: E402
from app.core.time_utils import prepare_for_mongo  # noqa: E402

DEFAULT_OWNER_EMAIL = "thesigntistslab@gmail.com"
SEED_BATCH_ID = "signguy-dev-sample-v1"
SEED_SOURCE = "development_sample_data"
ACTIVE_SEED_SCOPE = "unscoped"


CLEANUP_COLLECTIONS = [
    "assistant_insights",
    "assistant_messages",
    "assistant_conversations",
    "ai_generated_assets",
    "ai_studio_editable_drafts",
    "wrap_activity_events",
    "wrap_warranties",
    "wrap_schedules",
    "wrap_packets",
    "wrap_panel_plans",
    "wrap_design_scenes",
    "wrap_inspections",
    "wrap_coverage_plans",
    "wrap_projects",
    "wrap_vehicles",
    "webstore_activity_events",
    "webstore_ledger_entries",
    "webstore_buyer_orders",
    "webstore_launch_packets",
    "webstore_mockups",
    "webstore_artwork_files",
    "webstore_questionnaire_submissions",
    "webstore_products",
    "webstores",
    "webstore_owners",
    "daily_digests",
    "communication_preferences",
    "thread_messages",
    "message_threads",
    "internal_notes",
    "email_logs",
    "audit_events",
    "activity_events",
    "notifications",
    "announcements",
    "proof_versions",
    "proofs",
    "documents",
    "files",
    "supplier_order_log",
    "supplier_product_stock",
    "supplier_products",
    "supplier_warehouses",
    "vendors",
    "inventory_reservations",
    "inventory_movements",
    "inventory_items",
    "inventory_locations",
    "material_cost_history",
    "materials",
    "payroll_transactions",
    "payroll_snapshots",
    "pay_periods",
    "time_off_requests",
    "timesheets",
    "time_entries",
    "shifts",
    "schedules",
    "employees",
    "calendar_events",
    "tasks",
    "production_stage_instances",
    "production_workflow_instances",
    "payments",
    "invoice_line_items",
    "invoices",
    "work_orders",
    "order_items",
    "orders",
    "quote_line_items",
    "quote_revisions",
    "quotes",
    "intake_submissions",
    "customers",
    "feature_entitlements",
    "ai_credit_accounts",
]


CUSTOMERS = [
    ("Riverbend Coffee Company", "Maya Carter", "maya.carter@example.com", "555-0101", "102 River St", "Asheville", "NC"),
    ("Keystone Auto Glass", "Evan Miller", "evan.miller@example.com", "555-0102", "211 Depot Ave", "Boone", "NC"),
    ("Mountain View Landscaping", "Nora Green", "nora.green@example.com", "555-0103", "44 Pine Hill Rd", "Hendersonville", "NC"),
    ("Northside Youth Baseball", "Coach Aaron Price", "aaron.price@example.com", "555-0104", "18 Fieldhouse Ln", "Black Mountain", "NC"),
    ("Redline Motorsports", "Jules Reed", "jules.reed@example.com", "555-0105", "707 Speedway Dr", "Greenville", "SC"),
    ("Lakeview Dental", "Dr. Anika Shah", "anika.shah@example.com", "555-0106", "88 Lakeview Pkwy", "Morganton", "NC"),
    ("Blue Ridge Construction", "Caleb Stone", "caleb.stone@example.com", "555-0107", "301 Builder Ct", "Waynesville", "NC"),
    ("Main Street Bakery", "Elena Brooks", "elena.brooks@example.com", "555-0108", "9 Main St", "Brevard", "NC"),
    ("Summit Fitness Center", "Marcus Holt", "marcus.holt@example.com", "555-0109", "120 Summit Way", "Johnson City", "TN"),
    ("Pine Valley Fire Department", "Chief Dana Owens", "dana.owens@example.com", "555-0110", "55 Station Rd", "Pine Valley", "NC"),
    ("Oak & Iron Brewery", "Tessa Boone", "tessa.boone@example.com", "555-0111", "14 Taproom Ave", "Asheville", "NC"),
    ("Cedar Grove Church", "Paul Lane", "paul.lane@example.com", "555-0112", "600 Chapel Rd", "Marion", "NC"),
    ("Harbor House Realty", "Iris Cole", "iris.cole@example.com", "555-0113", "22 Market Sq", "Wilmington", "NC"),
    ("Peak Adventure Rentals", "Owen Hart", "owen.hart@example.com", "555-0114", "66 Ridge Trail", "Boone", "NC"),
    ("Metro Pet Clinic", "Leah Nguyen", "leah.nguyen@example.com", "555-0115", "400 Petcare Blvd", "Knoxville", "TN"),
    ("BrightPath Preschool", "Riley Foster", "riley.foster@example.com", "555-0116", "7 Learning Loop", "Hickory", "NC"),
    ("Silverline Plumbing", "Andre Walsh", "andre.walsh@example.com", "555-0117", "90 Service Rd", "Spartanburg", "SC"),
    ("GreenFork Market", "Priya Singh", "priya.singh@example.com", "555-0118", "33 Fresh Ave", "Greer", "SC"),
]


ITEM_TEMPLATES = [
    ("banners", "13 oz banner", "Grand opening banner with hems and grommets", 24800, "ea", True, True),
    ("yard_signs", "Coroplast yard signs", "Double-sided 18x24 coroplast signs with stakes", 1850, "ea", True, True),
    ("aluminum_signs", "Aluminum panel", "3 mm ACM exterior sign panel", 14200, "ea", True, True),
    ("storefront", "Channel letter service", "Storefront sign service and install package", 215000, "ea", True, True),
    ("vehicle_graphics", "Vehicle lettering", "Door lettering, rear window, and DOT numbers", 86500, "ea", True, True),
    ("wraps", "Partial vehicle wrap", "Printed and laminated partial wrap graphics", 285000, "ea", True, True),
    ("decals", "Contour-cut decals", "Outdoor contour-cut decals on gloss vinyl", 675, "ea", True, True),
    ("window_graphics", "Perforated window graphics", "One-way window perf graphics with laminate", 118000, "ea", True, True),
    ("wall_graphics", "Wall mural", "Printed wall graphic with installation", 172000, "ea", True, True),
    ("installation", "Installation labor", "Scheduled field installation labor", 12500, "hr", False, True),
    ("design", "Design service", "Layout and production art preparation", 9500, "hr", False, False),
]


MATERIALS = [
    ("BNR-13OZ-54", "13 oz Scrim Banner Vinyl", "banner_vinyl", "roll", 14800, 23000, 220, 60),
    ("VIN-GLOSS-54", "Gloss Permanent Vinyl", "vinyl", "roll", 18900, 32000, 180, 55),
    ("VIN-MATTE-54", "Matte Permanent Vinyl", "vinyl", "roll", 20100, 34000, 95, 50),
    ("VIN-CAST-WRAP", "Cast Wrap Vinyl", "wrap_vinyl", "roll", 65500, 94000, 70, 30),
    ("LAM-GLOSS-54", "Gloss UV Laminate", "laminate", "roll", 36500, 52000, 80, 35),
    ("LAM-MATTE-54", "Matte UV Laminate", "laminate", "roll", 39000, 55000, 38, 35),
    ("CORO-4MM-WHT", "4 mm White Coroplast", "rigid_substrate", "sheet", 1450, 2600, 120, 40),
    ("ACM-3MM-WHT", "3 mm White ACM Panel", "rigid_substrate", "sheet", 6450, 11800, 28, 20),
    ("ALUM-18X24", "18x24 Aluminum Blank", "rigid_substrate", "sheet", 875, 1600, 75, 30),
    ("PVC-3MM-WHT", "3 mm White PVC", "rigid_substrate", "sheet", 5125, 9600, 22, 12),
    ("FOAM-3/16", "3/16 Foam Board", "rigid_substrate", "sheet", 2410, 4100, 44, 20),
    ("TTAPE-12", "12 inch Transfer Tape", "application_supply", "roll", 7600, 11800, 18, 8),
    ("APP-FLUID", "Application Fluid", "application_supply", "gallon", 2850, 4200, 6, 4),
    ("INK-CMYK", "Eco-Solvent Ink Set", "ink", "set", 48200, 62000, 3, 2),
    ("GROM-NICKEL", "Nickel Grommets", "hardware", "box", 2200, 3600, 9, 4),
    ("HEMTAPE-1", "1 inch Banner Hem Tape", "hardware", "roll", 3300, 5000, 11, 5),
    ("MAG-030", "0.030 Magnetic Sheeting", "magnet", "roll", 41500, 61000, 5, 3),
    ("STAND-HWIRE", "H-Wire Yard Sign Stakes", "hardware", "bundle", 1850, 2800, 35, 20),
    ("STUD-ALUM", "Aluminum Mounting Studs", "hardware", "pack", 1450, 2400, 14, 8),
    ("TAPE-VHB", "VHB Mounting Tape", "hardware", "roll", 4100, 6200, 8, 4),
    ("CLEANER-PREP", "Surface Prep Cleaner", "application_supply", "quart", 1890, 2950, 13, 6),
    ("SQUEEGEE-FELT", "Felt Edge Squeegees", "tooling", "pack", 1275, 2100, 24, 8),
    ("MASK-PAPER", "Transfer Mask Paper", "application_supply", "roll", 9400, 14100, 7, 4),
    ("CANVAS-60", "Artist Canvas Print Media", "specialty_media", "roll", 28800, 43000, 4, 2),
    ("POSTER-SATIN", "Satin Poster Paper", "paper", "roll", 10900, 16500, 13, 5),
    ("SUBL-TAPE", "Heat Tape", "apparel_supply", "roll", 900, 1500, 20, 8),
    ("APP-HTV-BLK", "Black Heat Transfer Vinyl", "apparel_supply", "roll", 8500, 13000, 10, 5),
    ("APP-HTV-WHT", "White Heat Transfer Vinyl", "apparel_supply", "roll", 8500, 13000, 6, 5),
    ("BOX-TUBE", "Shipping Tubes", "shipping", "case", 5800, 8100, 16, 6),
    ("BOX-FLAT", "Flat Sign Shipping Cartons", "shipping", "case", 7800, 10800, 8, 4),
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | date) -> str:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return dt.isoformat()


def as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def at_day(base: datetime, days: int, hour: int = 9, minute: int = 0) -> datetime:
    target = (base + timedelta(days=days)).date()
    return datetime.combine(target, time(hour=hour, minute=minute), tzinfo=timezone.utc)


def seed_id(kind: str, key: str | int) -> str:
    return f"{SEED_BATCH_ID}:{ACTIVE_SEED_SCOPE}:{kind}:{key}"


def money(quantity: int | float, unit_cents: int, discount_cents: int = 0, taxable: bool = True) -> dict[str, int]:
    subtotal = int(round(quantity * unit_cents))
    tax = int(round(max(subtotal - discount_cents, 0) * 0.07)) if taxable else 0
    total = subtotal - discount_cents + tax
    return {"subtotal_cents": subtotal, "discount_cents": discount_cents, "tax_cents": tax, "total_cents": total}


def base_doc(tenant_id: str, kind: str, key: str | int, created_at: datetime) -> dict[str, Any]:
    return {
        "id": seed_id(kind, key),
        "tenant_id": tenant_id,
        "created_at": created_at,
        "updated_at": created_at + timedelta(hours=2),
        "is_dev_sample_data": True,
        "seed_batch_id": SEED_BATCH_ID,
        "seed_source": SEED_SOURCE,
    }


class Seeder:
    def __init__(self, tenant: dict[str, Any], user: dict[str, Any]) -> None:
        global ACTIVE_SEED_SCOPE
        self.tenant = tenant
        self.user = user
        self.tenant_id = tenant["id"]
        self.user_id = user["id"]
        ACTIVE_SEED_SCOPE = str(tenant.get("slug") or tenant["id"])
        self.now = utcnow()
        self.counts: dict[str, int] = defaultdict(int)

    async def upsert(self, collection: str, doc: dict[str, Any]) -> None:
        doc.setdefault("is_dev_sample_data", True)
        doc.setdefault("seed_batch_id", SEED_BATCH_ID)
        doc.setdefault("seed_source", SEED_SOURCE)
        existing = await db[collection].find_one({"id": doc["id"]})
        if existing and (existing.get("tenant_id") != self.tenant_id or existing.get("seed_batch_id") != SEED_BATCH_ID):
            raise RuntimeError(f"Refusing to overwrite non-sample record {collection}/{doc['id']}")
        await db[collection].replace_one({"id": doc["id"]}, prepare_for_mongo(doc), upsert=True)
        self.counts[collection] += 1

    async def seed_all(self) -> dict[str, int]:
        await self.seed_access_markers()
        customers = await self.seed_customers()
        intakes = await self.seed_intake(customers)
        quotes, quote_items = await self.seed_quotes(customers, intakes)
        orders, order_items = await self.seed_orders(customers, quotes, quote_items)
        invoices = await self.seed_invoices(orders, order_items)
        employees = await self.seed_team()
        work_orders, stages = await self.seed_production(customers, orders, order_items, employees)
        await self.seed_calendar(customers, orders, work_orders, employees)
        tasks = await self.seed_tasks(customers, quotes, orders, work_orders, employees)
        await self.seed_inventory(orders, order_items, work_orders)
        files = await self.seed_documents_and_proofs(customers, quotes, orders, work_orders)
        webstores = await self.seed_webstores(customers, files)
        await self.seed_wrap_lab(customers, quotes, orders, work_orders, files)
        await self.seed_comms_and_activity(customers, quotes, orders, work_orders, invoices, employees, tasks, webstores)
        return dict(sorted(self.counts.items()))

    async def seed_access_markers(self) -> None:
        features = [
            ("business_assistant", "Development sample entitlement so the current tenant can inspect Assistant UI locally."),
            ("studio_ai_tools", "Development sample entitlement so AI tool catalog screens can render locally."),
            ("webstores", "Development sample entitlement for local Webstore inspection."),
            ("wrap_lab", "Development sample entitlement for local Wrap Lab inspection."),
            ("team_payroll", "Development sample entitlement for local team and payroll inspection."),
        ]
        for key, notes in features:
            doc = base_doc(self.tenant_id, "feature-entitlement", key, self.now - timedelta(days=1))
            doc.update({
                "feature_key": key,
                "enabled": True,
                "quota": None,
                "quota_used": 0,
                "expires_at": None,
                "granted_by": self.user_id,
                "notes": notes,
            })
            await self.upsert("feature_entitlements", doc)
        credit = base_doc(self.tenant_id, "ai-credit-account", "current", self.now - timedelta(days=1))
        credit.update({
            "status": "active",
            "currency": "ai_credits",
            "balance": 0,
            "included_credits": 0,
            "purchased_credits": 0,
            "reserved_credits": 0,
            "billing_cycle_starts_at": iso(at_day(self.now, -10)),
            "billing_cycle_ends_at": iso(at_day(self.now, 20)),
            "notes": "Local sample account only. No commercial credit pricing is implied.",
        })
        await self.upsert("ai_credit_accounts", credit)

    async def seed_customers(self) -> list[dict[str, Any]]:
        customers: list[dict[str, Any]] = []
        for idx, (company, contact, email, phone, street, city, state) in enumerate(CUSTOMERS, start=1):
            created = self.now - timedelta(days=92 - idx * 4)
            customer = base_doc(self.tenant_id, "customer", idx, created)
            customer.update({
                "name": contact,
                "company": company,
                "email": email,
                "phone": phone,
                "address_line1": street,
                "address_line2": "Suite " + str(100 + idx) if idx % 5 == 0 else None,
                "city": city,
                "state": state,
                "postal_code": f"28{idx:03d}",
                "country": "US",
                "tags": ["development-sample", "repeat-customer" if idx in (1, 5, 8, 11) else "new-lead"],
                "billing_address": {"line1": street, "city": city, "state": state, "postal_code": f"28{idx:03d}"},
                "installation_address": {
                    "line1": street if idx % 3 else f"{idx} Commerce Park Dr",
                    "city": city,
                    "state": state,
                    "postal_code": f"28{idx:03d}",
                },
                "contacts": [
                    {"name": contact, "role": "Primary", "email": email, "phone": phone},
                    {
                        "name": f"{contact.split()[0]} Operations",
                        "role": "Install coordination",
                        "email": f"ops-{idx}@example.com",
                        "phone": f"555-02{idx:02d}",
                    },
                ][: 1 if idx > 10 else 2],
                "notes": "Development sample customer with fictional contact, billing, and installation details.",
                "archived": False,
            })
            await self.upsert("customers", customer)
            customers.append(customer)
        return customers

    async def seed_intake(self, customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        statuses = [
            "submitted",
            "reviewing",
            "needs_follow_up",
            "quote_created",
            "converted",
            "submitted",
            "reviewing",
            "quote_created",
            "declined",
            "submitted",
        ]
        intakes: list[dict[str, Any]] = []
        for idx in range(1, 11):
            customer = customers[idx - 1]
            created = self.now - timedelta(days=34 - idx * 3)
            tmpl = ITEM_TEMPLATES[(idx + 2) % len(ITEM_TEMPLATES)]
            intake = base_doc(self.tenant_id, "intake", idx, created)
            intake.update({
                "intake_number": f"INT-91{idx:03d}",
                "source_type": "internal_user" if idx % 2 else "public_form",
                "source_reference": "development-sample",
                "customer_id": customer["id"],
                "customer_name": customer["company"],
                "customer_email": customer["email"],
                "customer_phone": customer["phone"],
                "project_name": f"{customer['company']} {tmpl[1]} Request",
                "status": statuses[idx - 1],
                "requested_due_date": iso(at_day(self.now, idx + 4)),
                "follow_up_at": iso(at_day(self.now, -1 if idx == 3 else idx + 1, 10)),
                "notes": f"Fictional intake for {tmpl[2].lower()}.",
                "items": [
                    {
                        "id": seed_id("intake-item", idx),
                        "description": tmpl[2],
                        "category": tmpl[0],
                        "quantity": 12 if tmpl[0] in {"yard_signs", "decals"} else 1,
                        "measurements": {"width_inches": 48, "height_inches": 24, "source": "customer_provided"},
                        "category_inputs": {"material_hint": tmpl[1], "install_needed": tmpl[6]},
                        "conversion_status": "converted" if idx in (4, 5, 8) else "pending",
                        "pricing_status": "not_started" if idx in (1, 10) else "manual",
                    }
                ],
                "status_history": [
                    {"from": None, "to": "submitted", "at": iso(created), "actor_user_id": self.user_id},
                    {"from": "submitted", "to": statuses[idx - 1], "at": iso(created + timedelta(hours=6)), "actor_user_id": self.user_id},
                ],
                "created_by_user_id": self.user_id,
            })
            await self.upsert("intake_submissions", intake)
            intakes.append(intake)
        return intakes

    async def seed_quotes(
        self, customers: list[dict[str, Any]], intakes: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        statuses = ["draft", "sent", "sent", "approved", "approved", "declined", "expired", "converted", "converted", "converted", "sent", "draft"]
        quotes: list[dict[str, Any]] = []
        quote_items: dict[str, list[dict[str, Any]]] = {}
        for idx in range(1, 13):
            customer = customers[(idx - 1) % len(customers)]
            created = self.now - timedelta(days=58 - idx * 4)
            quote = base_doc(self.tenant_id, "quote", idx, created)
            line_docs: list[dict[str, Any]] = []
            line_total = {"subtotal_cents": 0, "discount_cents": 0, "tax_cents": 0, "total_cents": 0}
            for pos in range(1, 1 + (2 if idx % 3 else 3)):
                tmpl = ITEM_TEMPLATES[(idx + pos) % len(ITEM_TEMPLATES)]
                qty = 24 if tmpl[0] in {"yard_signs", "decals"} else (2 if pos == 2 and tmpl[0] != "installation" else 1)
                totals = money(qty, tmpl[3], 2500 if idx in (4, 9) and pos == 1 else 0, taxable=tmpl[0] != "design")
                for key in line_total:
                    line_total[key] += totals[key]
                item = base_doc(self.tenant_id, "quote-line-item", f"{idx}-{pos}", created + timedelta(minutes=pos))
                item.update({
                    "quote_id": quote["id"],
                    "revision_number": 1,
                    "position": pos,
                    "category": tmpl[0],
                    "product_type": tmpl[1],
                    "description": tmpl[2],
                    "quantity": qty,
                    "unit": tmpl[4],
                    "dimensions": {"width_inches": 48 + pos * 12, "height_inches": 24 + pos * 6},
                    "unit_price_cents": tmpl[3],
                    "discount_cents": totals["discount_cents"],
                    "tax_cents": totals["tax_cents"],
                    "line_subtotal_cents": totals["subtotal_cents"],
                    "line_total_cents": totals["total_cents"],
                    "production_required": tmpl[5],
                    "design_required": tmpl[0] in {"wraps", "storefront", "wall_graphics"},
                })
                await self.upsert("quote_line_items", item)
                line_docs.append(item)
            quote.update({
                "number": f"Q-91{idx:03d}",
                "customer_id": customer["id"],
                "job_name": f"{customer['company']} {line_docs[0]['product_type']}",
                "status": statuses[idx - 1],
                "revision_number": 1,
                "expires_at": iso(at_day(self.now, 12 - idx)),
                "follow_up_at": iso(at_day(self.now, -2 if idx == 2 else idx + 2, 11)),
                "notes_internal": "Development sample quote with connected line items.",
                "notes_customer": "Thank you for considering SignGuy AI for this fictional sample project.",
                "subtotal_cents": line_total["subtotal_cents"],
                "discount_cents": line_total["discount_cents"],
                "tax_cents": line_total["tax_cents"],
                "total_cents": line_total["total_cents"],
                "sent_at": iso(created + timedelta(days=1)) if statuses[idx - 1] in {"sent", "approved", "declined", "expired", "converted"} else None,
                "viewed_at": iso(created + timedelta(days=2)) if statuses[idx - 1] in {"approved", "declined", "converted"} else None,
                "approved_at": iso(created + timedelta(days=3)) if statuses[idx - 1] in {"approved", "converted"} else None,
                "declined_at": iso(created + timedelta(days=4)) if statuses[idx - 1] == "declined" else None,
                "created_by": self.user_id,
                "source_intake_id": intakes[(idx - 1) % len(intakes)]["id"] if idx <= 10 else None,
            })
            await self.upsert("quotes", quote)
            revision = base_doc(self.tenant_id, "quote-revision", idx, created)
            revision.update({
                "quote_id": quote["id"],
                "revision_number": 1,
                "status": "current",
                "snapshot": {"line_item_count": len(line_docs), "total_cents": quote["total_cents"]},
                "created_by": self.user_id,
            })
            await self.upsert("quote_revisions", revision)
            quotes.append(quote)
            quote_items[quote["id"]] = line_docs
        return quotes, quote_items

    async def seed_orders(
        self, customers: list[dict[str, Any]], quotes: list[dict[str, Any]], quote_items: dict[str, list[dict[str, Any]]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        statuses = ["confirmed", "in_production", "in_production", "ready", "completed", "confirmed", "cancelled", "completed", "in_production", "confirmed", "ready", "completed", "draft", "confirmed", "in_production", "completed"]
        orders: list[dict[str, Any]] = []
        all_items: list[dict[str, Any]] = []
        converted_quote_numbers = {8: quotes[7], 9: quotes[8], 10: quotes[9], 4: quotes[3], 5: quotes[4]}
        for idx in range(1, 17):
            quote = converted_quote_numbers.get(idx)
            customer = next((c for c in customers if quote and c["id"] == quote["customer_id"]), customers[(idx - 1) % len(customers)])
            created = (self.now - timedelta(days=42 - idx * 3)) if not quote else as_datetime(quote["approved_at"]) + timedelta(days=1)
            source = "quote" if quote else ("webstore" if idx in (6, 14) else ("wrap_lab" if idx in (3, 15) else "manual"))
            item_templates = quote_items.get(quote["id"], []) if quote else []
            line_total = {"subtotal_cents": 0, "discount_cents": 0, "tax_cents": 0, "total_cents": 0}
            order_item_count = len(item_templates) if item_templates else (2 + (1 if idx % 4 == 0 else 0))
            order_items: list[dict[str, Any]] = []
            for pos in range(1, order_item_count + 1):
                if item_templates:
                    source_item = item_templates[pos - 1]
                    tmpl = (
                        source_item["category"],
                        source_item["product_type"],
                        source_item["description"],
                        source_item["unit_price_cents"],
                        source_item["unit"],
                        source_item["production_required"],
                        True,
                    )
                    qty = source_item["quantity"]
                    totals = {
                        "subtotal_cents": source_item["line_subtotal_cents"],
                        "discount_cents": source_item["discount_cents"],
                        "tax_cents": source_item["tax_cents"],
                        "total_cents": source_item["line_total_cents"],
                    }
                else:
                    tmpl = ITEM_TEMPLATES[(idx + pos * 2) % len(ITEM_TEMPLATES)]
                    qty = 18 if tmpl[0] in {"yard_signs", "decals"} else (1 if tmpl[4] == "ea" else 3)
                    totals = money(qty, tmpl[3], taxable=tmpl[0] != "design")
                for key in line_total:
                    line_total[key] += totals[key]
                item = base_doc(self.tenant_id, "order-item", f"{idx}-{pos}", created + timedelta(minutes=pos))
                item.update({
                    "order_id": seed_id("order", idx),
                    "position": pos,
                    "category": tmpl[0],
                    "product_type": tmpl[1],
                    "description": tmpl[2],
                    "quantity": qty,
                    "unit": tmpl[4],
                    "dimensions": {"width_inches": 60, "height_inches": 36},
                    "unit_price_cents": tmpl[3],
                    "discount_cents": totals["discount_cents"],
                    "tax_cents": totals["tax_cents"],
                    "line_subtotal_cents": totals["subtotal_cents"],
                    "line_total_cents": totals["total_cents"],
                    "artwork_status": "approved" if idx in (5, 8, 12, 16) else ("needs_customer_artwork" if idx in (1, 13) else "in_progress"),
                    "proof_status": "approved" if idx in (5, 8, 12, 16) else ("awaiting_approval" if idx in (2, 9, 15) else "not_sent"),
                    "customer_supplied_artwork": idx in (1, 7, 10),
                    "design_required": tmpl[0] in {"wraps", "storefront", "wall_graphics", "vehicle_graphics"},
                    "production_required": tmpl[5],
                    "notes": "Connected development sample Order Item.",
                })
                await self.upsert("order_items", item)
                order_items.append(item)
                all_items.append(item)
            paid = 0
            if statuses[idx - 1] == "completed":
                paid = line_total["total_cents"]
            elif idx in (2, 9, 14):
                paid = int(line_total["total_cents"] * 0.5)
            order = base_doc(self.tenant_id, "order", idx, created)
            order.update({
                "number": f"O-91{idx:03d}",
                "customer_id": customer["id"],
                "order_source": source,
                "source_quote_id": quote["id"] if quote else None,
                "order_source_record_type": "quote" if quote else source,
                "order_source_record_id": quote["id"] if quote else None,
                "job_name": quote["job_name"] if quote else f"{customer['company']} {order_items[0]['product_type']}",
                "title": quote["job_name"] if quote else f"{customer['company']} {order_items[0]['product_type']}",
                "notes": "Development sample order connected to customer, items, production, invoices, and activity.",
                "subtotal_cents": line_total["subtotal_cents"],
                "discount_cents": line_total["discount_cents"],
                "tax_cents": line_total["tax_cents"],
                "total_cents": line_total["total_cents"],
                "amount_invoiced_cents": line_total["total_cents"] if idx <= 12 else 0,
                "amount_paid_cents": paid,
                "balance_cents": line_total["total_cents"] - paid,
                "due_date": iso(at_day(self.now, -4 if idx == 9 else idx + 5)),
                "status": statuses[idx - 1],
                "created_by": self.user_id,
            })
            await self.upsert("orders", order)
            orders.append(order)
            if quote:
                quote["status"] = "converted"
                quote["converted_order_id"] = order["id"]
                quote["converted_at"] = iso(created)
                await self.upsert("quotes", quote)
        return orders, all_items

    async def seed_invoices(self, orders: list[dict[str, Any]], order_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        invoices: list[dict[str, Any]] = []
        legacy_statuses = ["sent", "partially_paid", "overdue", "paid", "paid", "sent", "void", "paid", "partially_paid", "viewed", "overdue", "paid"]
        for idx, order in enumerate(orders[:12], start=1):
            created = as_datetime(order["created_at"]) + timedelta(days=1)
            legacy = legacy_statuses[idx - 1]
            paid = order["total_cents"] if legacy == "paid" else (int(order["total_cents"] * 0.5) if legacy == "partially_paid" else 0)
            financial = "paid" if legacy == "paid" else ("partial" if legacy == "partially_paid" else ("voided" if legacy == "void" else "unpaid"))
            balance = 0 if legacy in {"paid", "void"} else order["total_cents"] - paid
            invoice = base_doc(self.tenant_id, "invoice", idx, created)
            invoice.update({
                "number": f"INV-91{idx:03d}",
                "order_id": order["id"],
                "customer_id": order["customer_id"],
                "title": f"Invoice for {order['job_name']}",
                "status": legacy,
                "document_status": "void" if legacy == "void" else "issued",
                "financial_status": financial,
                "subtotal_cents": order["subtotal_cents"],
                "discount_cents": order["discount_cents"],
                "tax_cents": order["tax_cents"],
                "fee_cents": 0,
                "total_cents": 0 if legacy == "void" else order["total_cents"],
                "paid_cents": paid,
                "refunded_cents": 0,
                "balance_cents": balance,
                "issued_at": iso(created),
                "sent_at": iso(created + timedelta(hours=4)),
                "viewed_at": iso(created + timedelta(days=1)) if legacy in {"viewed", "partially_paid", "paid"} else None,
                "due_date": iso(at_day(self.now, -10 if legacy == "overdue" else 8 + idx)),
                "created_by": self.user_id,
            })
            await self.upsert("invoices", invoice)
            invoices.append(invoice)
            related_items = [i for i in order_items if i["order_id"] == order["id"]]
            for pos, item in enumerate(related_items, start=1):
                line = base_doc(self.tenant_id, "invoice-line-item", f"{idx}-{pos}", created + timedelta(minutes=pos))
                line.update({
                    "invoice_id": invoice["id"],
                    "order_id": order["id"],
                    "order_item_id": item["id"],
                    "position": pos,
                    "description": item["description"],
                    "quantity": item["quantity"],
                    "unit_price_cents": item["unit_price_cents"],
                    "line_total_cents": item["line_total_cents"],
                })
                await self.upsert("invoice_line_items", line)
            if paid > 0:
                for payment_idx, amount in enumerate(([int(paid * 0.5), paid - int(paid * 0.5)] if legacy == "paid" and idx % 2 == 0 else [paid]), start=1):
                    payment = base_doc(self.tenant_id, "payment", f"{idx}-{payment_idx}", created + timedelta(days=payment_idx))
                    payment.update({
                        "invoice_id": invoice["id"],
                        "customer_id": order["customer_id"],
                        "order_id": order["id"],
                        "source": "manual",
                        "status": "confirmed",
                        "amount_cents": amount,
                        "method": "check" if payment_idx == 1 else "card_manual",
                        "paid_on": iso((created + timedelta(days=payment_idx)).date()),
                        "received_at": iso(created + timedelta(days=payment_idx, hours=1)),
                        "reference": f"DEV-PAY-{idx:03d}-{payment_idx}",
                        "notes": "Local development sample payment. No processor transaction was created.",
                        "confirmed_at": iso(created + timedelta(days=payment_idx, hours=1)),
                        "created_by": self.user_id,
                        "idempotency_key": seed_id("payment-idempotency", f"{idx}-{payment_idx}"),
                    })
                    await self.upsert("payments", payment)
        return invoices

    async def seed_team(self) -> list[dict[str, Any]]:
        employees: list[dict[str, Any]] = []
        people = [
            ("Avery Black", "Owner / Administrator", "owner"),
            ("Camila Torres", "Designer", "designer"),
            ("Miles Bennett", "Production Specialist", "production"),
            ("Jordan Kim", "Installer", "installer"),
        ]
        week_start = self.now.date() - timedelta(days=(self.now.weekday() + 2) % 7)
        while True:
            existing_schedule = await db.schedules.find_one({"tenant_id": self.tenant_id, "period_start": iso(week_start)})
            if not existing_schedule or existing_schedule.get("seed_batch_id") == SEED_BATCH_ID:
                break
            week_start += timedelta(days=7)
        schedule = base_doc(self.tenant_id, "schedule", "current", at_day(self.now, -3))
        schedule.update({
            "period_start": iso(week_start),
            "period_end": iso(week_start + timedelta(days=6)),
            "status": "published",
            "title": "Current development sample team schedule",
            "published_at": iso(at_day(self.now, -1, 16)),
            "published_by_user_id": self.user_id,
        })
        await self.upsert("schedules", schedule)
        for idx, (name, role, department) in enumerate(people, start=1):
            employee = base_doc(self.tenant_id, "employee", idx, self.now - timedelta(days=120 - idx))
            employee.update({
                "name": name,
                "email": f"{name.lower().replace(' ', '.')}@example.com",
                "phone": f"555-03{idx:02d}",
                "role": role,
                "department": department,
                "status": "active",
                "linked_user_id": self.user_id if idx == 1 else None,
                "pay_type": "hourly" if idx > 1 else "salary",
                "hourly_rate_cents": 2200 + idx * 350,
                "status_history": [{"from": None, "to": "active", "at": iso(self.now - timedelta(days=120 - idx)), "reason": "Development sample"}],
            })
            await self.upsert("employees", employee)
            employees.append(employee)
            for day in range(0, 5):
                start = datetime.combine(week_start + timedelta(days=day), time(8 + (idx % 2), 0), tzinfo=timezone.utc)
                shift = base_doc(self.tenant_id, "shift", f"{idx}-{day}", start - timedelta(days=1))
                shift.update({
                    "schedule_id": schedule["id"],
                    "employee_id": employee["id"],
                    "title": f"{role} shift",
                    "start_at": iso(start),
                    "end_at": iso(start + timedelta(hours=8)),
                    "status": "published",
                    "department": department,
                    "location": "Main shop" if department != "installer" else "Field",
                })
                await self.upsert("shifts", shift)
        pay_period = base_doc(self.tenant_id, "pay-period", "current", at_day(self.now, -14))
        pay_period.update({
            "period_start": iso(week_start - timedelta(days=7)),
            "period_end": iso(week_start - timedelta(days=1)),
            "status": "closed",
            "label": "Development sample prior week",
        })
        await self.upsert("pay_periods", pay_period)
        for idx, employee in enumerate(employees, start=1):
            for day in range(1, 4):
                clock_in = at_day(self.now, -day, 8 + idx % 2)
                open_entry = idx == 3 and day == 1
                entry = base_doc(self.tenant_id, "time-entry", f"{idx}-{day}", clock_in)
                entry.update({
                    "employee_id": employee["id"],
                    "work_date": iso(clock_in.date()),
                    "clock_in_at": iso(clock_in),
                    "clock_out_at": None if open_entry else iso(clock_in + timedelta(hours=8, minutes=15 if idx == 4 else 0)),
                    "status": "open" if open_entry else "closed",
                    "source": "time_clock",
                    "manual_adjustment": idx == 2 and day == 2,
                    "adjustment_reason": "Manager-approved correction for lunch break." if idx == 2 and day == 2 else None,
                })
                await self.upsert("time_entries", entry)
            sheet = base_doc(self.tenant_id, "timesheet", idx, at_day(self.now, -7))
            sheet.update({
                "employee_id": employee["id"],
                "week_start": iso(week_start - timedelta(days=7)),
                "week_end": iso(week_start - timedelta(days=1)),
                "status": "approved" if idx != 3 else "needs_review",
                "regular_minutes": 2400 if idx != 3 else 1980,
                "overtime_minutes": 90 if idx == 4 else 0,
                "approved_by_user_id": self.user_id if idx != 3 else None,
                "approved_at": iso(at_day(self.now, -2, 15)) if idx != 3 else None,
            })
            await self.upsert("timesheets", sheet)
            payroll = base_doc(self.tenant_id, "payroll-snapshot", idx, at_day(self.now, -2))
            payroll.update({
                "pay_period_id": pay_period["id"],
                "employee_id": employee["id"],
                "status": "ready",
                "gross_pay_cents": 92000 + idx * 13000,
                "regular_minutes": sheet["regular_minutes"],
                "overtime_minutes": sheet["overtime_minutes"],
                "adjustments_cents": 1500 if idx == 2 else 0,
            })
            await self.upsert("payroll_snapshots", payroll)
            txn = base_doc(self.tenant_id, "payroll-transaction", idx, at_day(self.now, -1))
            txn.update({
                "payroll_snapshot_id": payroll["id"],
                "employee_id": employee["id"],
                "transaction_type": "earning",
                "amount_cents": payroll["gross_pay_cents"],
                "memo": "Development sample payroll transaction.",
            })
            await self.upsert("payroll_transactions", txn)
        time_off = base_doc(self.tenant_id, "time-off", "installer-vacation", at_day(self.now, -3))
        time_off.update({
            "employee_id": employees[3]["id"],
            "requested_by_employee_id": employees[3]["id"],
            "reviewed_by_user_id": self.user_id,
            "start_at": iso(at_day(self.now, 14, 0)),
            "end_at": iso(at_day(self.now, 15, 23, 59)),
            "all_day": True,
            "status": "approved",
            "request_type": "vacation",
            "reason": "Fictional planned time off.",
            "approved_at": iso(at_day(self.now, -1, 13)),
            "history": [{"to": "approved", "at": iso(at_day(self.now, -1, 13)), "actor_user_id": self.user_id}],
        })
        await self.upsert("time_off_requests", time_off)
        announcement = base_doc(self.tenant_id, "announcement", "laminator", at_day(self.now, -2))
        announcement.update({
            "title": "Laminator maintenance window",
            "body": "Development sample notice: reserve extra finishing time Tuesday morning.",
            "status": "published",
            "audience": "all",
            "published_at": iso(at_day(self.now, -1, 8)),
            "created_by_user_id": self.user_id,
        })
        await self.upsert("announcements", announcement)
        return employees

    async def seed_production(
        self, customers: list[dict[str, Any]], orders: list[dict[str, Any]], order_items: list[dict[str, Any]], employees: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        statuses = ["queued", "in_progress", "in_progress", "ready", "completed", "released", "on_hold", "completed", "in_progress", "queued", "ready", "completed", "draft", "in_progress"]
        work_orders: list[dict[str, Any]] = []
        stages: list[dict[str, Any]] = []
        production_items = [item for item in order_items if item.get("production_required")][:14]
        stage_defs = [
            ("artwork", "Artwork Prep"),
            ("proof", "Proof Review"),
            ("print", "Print"),
            ("finish", "Finish / QC"),
            ("install", "Install or Pickup"),
        ]
        for idx, item in enumerate(production_items, start=1):
            order = next(o for o in orders if o["id"] == item["order_id"])
            created = as_datetime(order["created_at"]) + timedelta(hours=8)
            work = base_doc(self.tenant_id, "work-order", idx, created)
            work.update({
                "number": f"WO-91{idx:03d}",
                "order_id": order["id"],
                "customer_id": order["customer_id"],
                "production_status": statuses[idx - 1],
                "priority": "rush" if idx in (2, 9) else ("high" if idx in (3, 7, 14) else "normal"),
                "due_date": iso(at_day(self.now, -2 if idx == 9 else idx + 3)),
                "assigned_user_ids": [self.user_id],
                "assigned_to": employees[(idx % 3) + 1]["name"],
                "department": "installation" if item["category"] in {"installation", "wraps", "vehicle_graphics"} else "production",
                "summary": f"Work Order Summary for {item['description']}",
                "items_snapshot": [{"order_item_id": item["id"], "description": item["description"], "quantity": item["quantity"]}],
                "created_by": self.user_id,
            })
            await self.upsert("work_orders", work)
            work_orders.append(work)
            workflow = base_doc(self.tenant_id, "production-workflow-instance", idx, created)
            workflow.update({
                "order_id": order["id"],
                "order_item_id": item["id"],
                "work_order_id": work["id"],
                "source_type": "manual_no_workflow",
                "source_name": "Development sample workflow",
                "created_by_user_id": self.user_id,
                "status": "completed" if statuses[idx - 1] == "completed" else "active",
                "resolution_source": "development_sample",
                "stage_definitions": [{"stage_key": k, "display_name": v, "sequence": n + 1} for n, (k, v) in enumerate(stage_defs)],
            })
            await self.upsert("production_workflow_instances", workflow)
            for seq, (key, name) in enumerate(stage_defs, start=1):
                if statuses[idx - 1] == "completed":
                    stage_status = "completed"
                elif statuses[idx - 1] == "on_hold" and seq == 3:
                    stage_status = "blocked"
                elif statuses[idx - 1] in {"ready"} and seq < 5:
                    stage_status = "completed"
                elif statuses[idx - 1] == "in_progress" and seq == 3:
                    stage_status = "in_progress"
                elif statuses[idx - 1] == "queued":
                    stage_status = "not_started"
                else:
                    stage_status = "waiting"
                due = at_day(self.now, -1 if idx == 9 and seq == 3 else idx + seq)
                stage = base_doc(self.tenant_id, "production-stage", f"{idx}-{seq}", created + timedelta(minutes=seq))
                stage.update({
                    "workflow_instance_id": workflow["id"],
                    "order_id": order["id"],
                    "order_item_id": item["id"],
                    "work_order_id": work["id"],
                    "stage_key": key,
                    "stage_name": name,
                    "sequence": seq,
                    "status": stage_status,
                    "assigned_employee_id": employees[(seq + idx) % len(employees)]["id"],
                    "assigned_user_id": self.user_id if seq == 1 else None,
                    "assigned_role": name,
                    "due_at": iso(due),
                    "started_at": iso(due - timedelta(hours=3)) if stage_status in {"in_progress", "completed"} else None,
                    "completed_at": iso(due - timedelta(hours=1)) if stage_status == "completed" else None,
                    "blocked_at": iso(due - timedelta(hours=2)) if stage_status == "blocked" else None,
                    "blocker_reason": "Awaiting customer artwork approval." if stage_status == "blocked" else None,
                    "history": [{"to": stage_status, "at": iso(created + timedelta(hours=seq)), "actor_user_id": self.user_id}],
                })
                await self.upsert("production_stage_instances", stage)
                stages.append(stage)
        return work_orders, stages

    async def seed_calendar(
        self, customers: list[dict[str, Any]], orders: list[dict[str, Any]], work_orders: list[dict[str, Any]], employees: list[dict[str, Any]]
    ) -> None:
        event_types = ["site_survey", "customer_meeting", "production_milestone", "installation", "vehicle_dropoff", "vehicle_pickup", "consultation", "installation", "custom", "production_milestone", "customer_meeting", "installation"]
        titles = [
            "Riverbend site survey",
            "Lakeview Dental design review",
            "Banner print deadline",
            "Redline Motorsports partial wrap install",
            "Peak Adventure vehicle dropoff",
            "Peak Adventure vehicle pickup",
            "GreenFork storefront consultation",
            "Blue Ridge exterior panel install",
            "Team production load review",
            "Northside jersey pickup deadline",
            "Main Street Bakery proof approval call",
            "Pine Valley apparatus lettering install",
        ]
        for idx, title in enumerate(titles, start=1):
            start = at_day(self.now, -8 + idx * 2, 9 + (idx % 5), 0)
            event = base_doc(self.tenant_id, "calendar-event", idx, start - timedelta(days=1))
            order = orders[(idx - 1) % len(orders)]
            work = work_orders[(idx - 1) % len(work_orders)] if work_orders else None
            event.update({
                "event_type": event_types[idx - 1],
                "title": title,
                "description": "Development sample calendar event connected to seeded business records.",
                "start_at": iso(start),
                "end_at": iso(start + timedelta(hours=2 if event_types[idx - 1] == "installation" else 1)),
                "status": "completed" if idx <= 3 else "scheduled",
                "customer_id": customers[(idx - 1) % len(customers)]["id"],
                "order_id": order["id"],
                "work_order_id": work["id"] if work else None,
                "employee_id": employees[idx % len(employees)]["id"],
                "location": order.get("job_name"),
                "visibility": "internal",
                "source_type": "work_order" if work else "appointment",
                "source_id": work["id"] if work else order["id"],
                "created_by_user_id": self.user_id,
            })
            await self.upsert("calendar_events", event)

    async def seed_tasks(
        self, customers: list[dict[str, Any]], quotes: list[dict[str, Any]], orders: list[dict[str, Any]], work_orders: list[dict[str, Any]], employees: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        statuses = ["not_started", "in_progress", "waiting", "blocked", "completed"] * 4
        priorities = ["low", "normal", "high", "rush"]
        tasks: list[dict[str, Any]] = []
        for idx in range(1, 21):
            created = self.now - timedelta(days=20 - idx)
            status = statuses[idx - 1]
            task = base_doc(self.tenant_id, "task", idx, created)
            order = orders[(idx - 1) % len(orders)]
            quote = quotes[(idx - 1) % len(quotes)]
            work = work_orders[(idx - 1) % len(work_orders)] if work_orders else None
            task.update({
                "title": [
                    "Follow up on quote approval",
                    "Confirm installation access",
                    "Prepare artwork proof",
                    "Check low-stock laminate",
                    "Close paid invoice",
                ][(idx - 1) % 5],
                "description": "Development sample task connected to seeded workflow records.",
                "status": status,
                "priority": priorities[idx % len(priorities)],
                "source": "development_sample",
                "customer_id": customers[(idx - 1) % len(customers)]["id"] if idx % 2 else None,
                "quote_id": quote["id"] if idx % 3 == 0 else None,
                "order_id": order["id"] if idx % 3 != 0 else None,
                "work_order_id": work["id"] if work and idx % 4 == 0 else None,
                "assigned_user_id": self.user_id if idx % 5 else None,
                "assigned_employee_id": employees[idx % len(employees)]["id"] if idx % 2 else None,
                "due_at": iso(at_day(self.now, -3 if idx in (4, 9, 14) else idx - 6, 15)),
                "start_at": iso(at_day(self.now, idx - 8, 9)),
                "completed_at": iso(created + timedelta(days=1)) if status == "completed" else None,
                "created_by_user_id": self.user_id,
            })
            await self.upsert("tasks", task)
            tasks.append(task)
        return tasks

    async def seed_inventory(self, orders: list[dict[str, Any]], order_items: list[dict[str, Any]], work_orders: list[dict[str, Any]]) -> None:
        vendors = [
            ("Graphic Supply Depot", "GSD", "materials@example.com"),
            ("Metro Sign Supply", "MSS", "orders@example.com"),
            ("WrapPro Distribution", "WPD", "wraps@example.com"),
            ("Apparel Print Source", "APS", "apparel@example.com"),
        ]
        locations = ["Main Rack", "Roll Media Wall", "Install Van"]
        for idx, (name, code, email) in enumerate(vendors, start=1):
            vendor = base_doc(self.tenant_id, "vendor", idx, self.now - timedelta(days=80 - idx))
            vendor.update({"name": name, "code": code, "email": email, "phone": f"555-04{idx:02d}", "active": True})
            await self.upsert("vendors", vendor)
            warehouse = base_doc(self.tenant_id, "supplier-warehouse", idx, self.now - timedelta(days=70 - idx))
            warehouse.update({"vendor_id": vendor["id"], "code": f"{code}-AVL", "name": f"{name} Asheville DC", "active": True})
            await self.upsert("supplier_warehouses", warehouse)
        for idx, location_name in enumerate(locations, start=1):
            location = base_doc(self.tenant_id, "inventory-location", idx, self.now - timedelta(days=65 - idx))
            location.update({"name": location_name, "description": "Development sample inventory location.", "active": True})
            await self.upsert("inventory_locations", location)
        for idx, (sku, name, category, unit, cost, charge, on_hand, reorder) in enumerate(MATERIALS, start=1):
            material = base_doc(self.tenant_id, "material", idx, self.now - timedelta(days=60 - idx))
            material.update({
                "sku": sku,
                "name": name,
                "category": category,
                "purchase_unit": unit,
                "inventory_unit": "sqft" if category in {"banner_vinyl", "vinyl", "wrap_vinyl", "laminate"} else unit,
                "cost_cents": cost,
                "suggested_charge_cents": charge,
                "active": True,
                "notes": "Development sample material.",
            })
            await self.upsert("materials", material)
            cost_history = base_doc(self.tenant_id, "material-cost-history", idx, self.now - timedelta(days=45 - idx))
            cost_history.update({"material_id": material["id"], "unit_cost_cents": cost, "source": "manual", "effective_at": iso(self.now - timedelta(days=45 - idx))})
            await self.upsert("material_cost_history", cost_history)
            loc_idx = (idx % len(locations)) + 1
            inventory_item = base_doc(self.tenant_id, "inventory-item", idx, self.now - timedelta(days=30 - idx))
            inventory_item.update({
                "material_id": material["id"],
                "location_id": seed_id("inventory-location", loc_idx),
                "quantity_on_hand": on_hand,
                "quantity_reserved": 5 if idx % 5 == 0 else 0,
                "reorder_point": reorder,
                "status": "low_stock" if on_hand <= reorder else "in_stock",
            })
            await self.upsert("inventory_items", inventory_item)
            movement = base_doc(self.tenant_id, "inventory-movement", idx, self.now - timedelta(days=idx % 12))
            movement.update({
                "material_id": material["id"],
                "location_id": seed_id("inventory-location", loc_idx),
                "movement_type": "receipt" if idx % 4 else "usage",
                "quantity_delta": 25 if idx % 4 else -8,
                "source_entity_type": "work_order" if work_orders and idx % 4 == 0 else "adjustment",
                "source_entity_id": work_orders[(idx - 1) % len(work_orders)]["id"] if work_orders and idx % 4 == 0 else seed_id("inventory-adjustment", idx),
                "idempotency_key": seed_id("inventory-movement-key", idx),
                "notes": "Development sample inventory movement.",
            })
            await self.upsert("inventory_movements", movement)
            supplier = base_doc(self.tenant_id, "supplier-product", idx, self.now - timedelta(days=20 - idx % 9))
            supplier.update({
                "vendor_id": seed_id("vendor", (idx % 4) + 1),
                "supplier_sku": f"{sku}-SUP",
                "name": name,
                "category": category,
                "family": category,
                "compatible_group": category,
                "unit_cost_cents": cost,
                "active": True,
            })
            await self.upsert("supplier_products", supplier)
            stock = base_doc(self.tenant_id, "supplier-product-stock", idx, self.now - timedelta(days=idx % 5))
            stock.update({
                "supplier_product_id": supplier["id"],
                "warehouse_id": seed_id("supplier-warehouse", (idx % 4) + 1),
                "quantity_available": 120 - idx,
                "lead_time_days": 1 + (idx % 5),
                "status": "available" if idx % 7 else "limited",
            })
            await self.upsert("supplier_product_stock", stock)
            if idx <= 6:
                reservation = base_doc(self.tenant_id, "inventory-reservation", idx, self.now - timedelta(days=idx))
                item = order_items[(idx - 1) % len(order_items)]
                reservation.update({
                    "material_id": material["id"],
                    "location_id": seed_id("inventory-location", loc_idx),
                    "quantity": 5 + idx,
                    "active": True,
                    "source_entity_type": "order_item",
                    "source_entity_id": item["id"],
                    "expires_at": iso(at_day(self.now, idx + 5)),
                })
                await self.upsert("inventory_reservations", reservation)

    async def seed_documents_and_proofs(
        self, customers: list[dict[str, Any]], quotes: list[dict[str, Any]], orders: list[dict[str, Any]], work_orders: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        categories = ["artwork", "quote_pdf", "invoice_pdf", "installation_photo", "measurement", "questionnaire", "customer_artwork", "contract", "aftercare", "proof"]
        files: list[dict[str, Any]] = []
        for idx in range(1, 17):
            created = self.now - timedelta(days=18 - idx)
            category = categories[(idx - 1) % len(categories)]
            file_doc = base_doc(self.tenant_id, "file", idx, created)
            file_doc.update({
                "filename": f"{category.replace('_', '-')}-{idx}.pdf",
                "original_filename": f"{category.replace('_', '-')}-{idx}.pdf",
                "storage_path": f"dev-sample/{self.tenant_id}/{category}-{idx}.pdf",
                "storage_key": f"dev-sample/{self.tenant_id}/{category}-{idx}.pdf",
                "content_type": "application/pdf",
                "mime_type": "application/pdf",
                "size_bytes": 2048 + idx * 128,
                "uploaded_by": self.user_id,
                "metadata": {"placeholder": True, "dev_sample": True},
            })
            await self.upsert("files", file_doc)
            files.append(file_doc)
            doc = base_doc(self.tenant_id, "document", idx, created + timedelta(minutes=3))
            doc.update({
                "customer_id": customers[(idx - 1) % len(customers)]["id"],
                "category": category if category != "proof" else "artwork",
                "source_type": "generated" if category in {"quote_pdf", "invoice_pdf", "proof"} else "upload",
                "title": f"{category.replace('_', ' ').title()} - development sample",
                "current_file_id": file_doc["id"],
                "archived": False,
                "parent_type": "order" if idx % 2 else "quote",
                "parent_id": orders[(idx - 1) % len(orders)]["id"] if idx % 2 else quotes[(idx - 1) % len(quotes)]["id"],
                "created_by_user_id": self.user_id,
            })
            await self.upsert("documents", doc)
        for idx in range(1, 9):
            order = orders[(idx - 1) % len(orders)]
            proof = base_doc(self.tenant_id, "proof", idx, self.now - timedelta(days=12 - idx))
            proof.update({
                "number": f"PRF-91{idx:03d}",
                "parent_type": "order",
                "parent_id": order["id"],
                "customer_id": order["customer_id"],
                "title": f"Proof for {order['job_name']}",
                "status": "approved" if idx in (2, 5, 8) else ("awaiting_customer" if idx in (3, 6) else "draft"),
                "current_version": 1,
                "created_by_user_id": self.user_id,
            })
            await self.upsert("proofs", proof)
            version = base_doc(self.tenant_id, "proof-version", idx, self.now - timedelta(days=11 - idx))
            version.update({
                "proof_id": proof["id"],
                "version": 1,
                "file_id": files[(idx - 1) % len(files)]["id"],
                "notes": "Development sample proof version.",
                "created_by_user_id": self.user_id,
            })
            await self.upsert("proof_versions", version)
        return files

    async def seed_webstores(self, customers: list[dict[str, Any]], files: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stores = [
            ("Northside Baseball Fundraiser", "fundraiser", "live"),
            ("Summit Fitness Staff Store", "employee", "approved"),
            ("Pine Valley Safety Day", "event", "closing_soon"),
            ("Riverbend Coffee Merch", "promotional", "draft"),
        ]
        webstores: list[dict[str, Any]] = []
        for idx, (name, store_type, status) in enumerate(stores, start=1):
            customer = customers[[3, 8, 9, 0][idx - 1]]
            owner = base_doc(self.tenant_id, "webstore-owner", idx, self.now - timedelta(days=30 - idx * 3))
            owner.update({
                "name": customer["name"],
                "email": customer["email"],
                "phone": customer["phone"],
                "organization": customer["company"],
                "customer_id": customer["id"],
                "stripe_onboarding_status": "not_required",
                "status": "active",
            })
            await self.upsert("webstore_owners", owner)
            store = base_doc(self.tenant_id, "webstore", idx, self.now - timedelta(days=24 - idx * 4))
            store.update({
                "owner_id": owner["id"],
                "name": name,
                "slug": f"dev-{idx}-{name.lower().replace(' ', '-')}",
                "store_type": store_type,
                "status": status,
                "description": f"Development sample {store_type} Webstore for {customer['company']}.",
                "branding": {"primary_color": ["#0f766e", "#7c3aed", "#dc2626", "#2563eb"][idx - 1]},
                "checkout_enabled": False,
                "terms_fee_acknowledged": True,
                "direct_owner_payout_required": False,
                "stripe_onboarding_required": False,
                "stripe_payment_ready": False,
                "public_url": f"https://example.com/dev-stores/{idx}",
                "deadline_at": iso(at_day(self.now, 12 + idx)),
                "launched_at": iso(at_day(self.now, -8)) if status in {"live", "closing_soon"} else None,
                "closed_at": iso(at_day(self.now, 4)) if status == "closed" else None,
            })
            await self.upsert("webstores", store)
            webstores.append(store)
            products = [
                ("Logo T-Shirt", "apparel", 1450, 2400, 350),
                ("Decal Pack", "decals", 420, 900, 150),
                ("Yard Sign", "yard_signs", 850, 1800, 300),
            ]
            product_ids: list[str] = []
            for pos, (product_name, category, cost, sell, share) in enumerate(products, start=1):
                product = base_doc(self.tenant_id, "webstore-product", f"{idx}-{pos}", self.now - timedelta(days=18 - idx))
                product.update({
                    "webstore_id": store["id"],
                    "name": product_name,
                    "description": f"{name} {product_name.lower()}",
                    "category": category,
                    "product_type": product_name,
                    "sku": f"DEV-WS{idx}-{pos}",
                    "production_cost_cents": cost,
                    "selling_price_cents": sell,
                    "store_owner_share_cents": share,
                    "platform_fee_basis_points": 150,
                    "variants": [{"name": "Standard", "options": ["S", "M", "L", "XL"] if category == "apparel" else ["One size"]}],
                    "personalization_enabled": category == "apparel",
                    "image_file_ids": [files[(idx + pos) % len(files)]["id"]],
                    "production_notes": "Development sample Webstore product.",
                    "public": status in {"live", "closing_soon"},
                    "featured": pos == 1,
                    "status": "active" if status in {"live", "closing_soon", "approved"} else "draft",
                })
                await self.upsert("webstore_products", product)
                product_ids.append(product["id"])
            q = base_doc(self.tenant_id, "webstore-questionnaire", idx, self.now - timedelta(days=17 - idx))
            q.update({
                "webstore_id": store["id"],
                "owner_id": owner["id"],
                "answers": {"audience": store_type, "deadline": store["deadline_at"], "pickup_plan": "shop pickup"},
                "known_products": [{"name": "Logo T-Shirt"}, {"name": "Yard Sign"}],
                "open_to_suggestions": True,
                "status": "submitted" if status != "draft" else "pending",
                "submitted_at": iso(at_day(self.now, -10 + idx)) if status != "draft" else None,
            })
            await self.upsert("webstore_questionnaire_submissions", q)
            artwork = base_doc(self.tenant_id, "webstore-artwork", idx, self.now - timedelta(days=14 - idx))
            artwork.update({
                "webstore_id": store["id"],
                "uploaded_by_actor_type": "staff",
                "uploaded_by_id": self.user_id,
                "original_file_id": files[idx % len(files)]["id"],
                "file_name": f"webstore-{idx}-logo.pdf",
                "file_type": "application/pdf",
                "artwork_status": "approved_for_production" if status in {"live", "closing_soon"} else "cleanup_pending",
                "quality_score": 86 + idx,
                "shop_approved_for_mockups": status != "draft",
                "shop_approved_for_production": status in {"live", "closing_soon"},
            })
            await self.upsert("webstore_artwork_files", artwork)
            mockup = base_doc(self.tenant_id, "webstore-mockup", idx, self.now - timedelta(days=13 - idx))
            mockup.update({
                "webstore_id": store["id"],
                "product_id": product_ids[0],
                "artwork_id": artwork["id"],
                "mockup_file_id": files[(idx + 4) % len(files)]["id"],
                "generation_source": "manual",
                "status": "owner_approved" if status in {"live", "closing_soon"} else "generated",
                "shop_approved": True,
                "owner_visible": status != "draft",
                "owner_approved": status in {"live", "closing_soon"},
            })
            await self.upsert("webstore_mockups", mockup)
            packet = base_doc(self.tenant_id, "webstore-launch-packet", idx, self.now - timedelta(days=12 - idx))
            packet.update({
                "webstore_id": store["id"],
                "status": "owner_approved" if status in {"live", "closing_soon"} else "generated",
                "snapshot": {"product_count": len(product_ids), "store_status": status},
                "pricing_summary": {"local_only": True, "no_stripe_records": True},
                "promotion_copy": "Development sample promotion copy.",
                "share_url": store["public_url"],
                "sent_at": iso(at_day(self.now, -9 + idx)) if status != "draft" else None,
            })
            await self.upsert("webstore_launch_packets", packet)
            if status != "draft":
                for order_idx in range(1, 3):
                    buyer = base_doc(self.tenant_id, "webstore-buyer-order", f"{idx}-{order_idx}", self.now - timedelta(days=7 - idx + order_idx))
                    subtotal = 2400 + order_idx * 900
                    tax = int(subtotal * 0.07)
                    buyer.update({
                        "webstore_id": store["id"],
                        "buyer_name": f"Sample Buyer {idx}-{order_idx}",
                        "buyer_email": f"buyer-{idx}-{order_idx}@example.com",
                        "buyer_phone": f"555-05{idx}{order_idx}",
                        "line_items": [{"product_id": product_ids[order_idx % len(product_ids)], "quantity": 1, "unit_price_cents": subtotal}],
                        "product_subtotal_cents": subtotal,
                        "donation_cents": 500 if store_type == "fundraiser" else 0,
                        "shipping_cents": 0,
                        "tax_cents": tax,
                        "total_cents": subtotal + tax + (500 if store_type == "fundraiser" else 0),
                        "status": "paid" if status in {"live", "closing_soon"} else "in_review",
                        "payment_status": "local_sample_paid" if status in {"live", "closing_soon"} else "pending",
                        "fulfillment_status": "ready_for_production" if status in {"live", "closing_soon"} else "not_started",
                        "idempotency_key": seed_id("webstore-buyer-order-key", f"{idx}-{order_idx}"),
                    })
                    await self.upsert("webstore_buyer_orders", buyer)
                    platform_fee = int(buyer["product_subtotal_cents"] * 0.015)
                    for entry_type, amount in [("buyer_payment", buyer["total_cents"]), ("platform_usage_fee", platform_fee), ("store_owner_share", 300)]:
                        ledger = base_doc(self.tenant_id, "webstore-ledger", f"{idx}-{order_idx}-{entry_type}", self.now - timedelta(days=6 - idx + order_idx))
                        ledger.update({
                            "webstore_id": store["id"],
                            "buyer_order_id": buyer["id"],
                            "entry_type": entry_type,
                            "amount_cents": amount,
                            "basis_amount_cents": buyer["product_subtotal_cents"],
                            "snapshot_basis_points": 150 if entry_type == "platform_usage_fee" else None,
                            "source_type": "webstore_buyer_order",
                            "source_id": buyer["id"],
                            "status": "posted",
                            "notes": "Local sample ledger only. No Stripe or payout action was created.",
                        })
                        await self.upsert("webstore_ledger_entries", ledger)
            activity = base_doc(self.tenant_id, "webstore-activity", idx, self.now - timedelta(days=idx))
            activity.update({
                "webstore_id": store["id"],
                "actor_type": "staff",
                "actor_id": self.user_id,
                "actor_email": self.user["email"],
                "action": "status.reviewed",
                "entity_type": "webstore",
                "entity_id": store["id"],
                "summary": f"Development sample Webstore {name} is {status}.",
            })
            await self.upsert("webstore_activity_events", activity)
        return webstores

    async def seed_wrap_lab(
        self, customers: list[dict[str, Any]], quotes: list[dict[str, Any]], orders: list[dict[str, Any]], work_orders: list[dict[str, Any]], files: list[dict[str, Any]]
    ) -> None:
        wrap_defs = [
            (4, "2024", "Ford", "Transit", "van", "partial_wrap", "design_in_progress"),
            (1, "2022", "Chevrolet", "Silverado", "pickup", "spot_graphics", "proof_ready"),
            (14, "2021", "Mercedes-Benz", "Sprinter", "sprinter_van", "full_wrap", "install_scheduled"),
            (5, "2020", "Dodge", "Challenger", "race_car", "half_wrap", "completed"),
        ]
        for idx, (customer_idx, year, make, model, vehicle_type, coverage, status) in enumerate(wrap_defs, start=1):
            customer = customers[customer_idx]
            vehicle = base_doc(self.tenant_id, "wrap-vehicle", idx, self.now - timedelta(days=28 - idx))
            vehicle.update({
                "customer_id": customer["id"],
                "year": year,
                "make": make,
                "model": model,
                "trim": "Development sample trim",
                "license_plate": f"DEVW{idx}23",
                "color": ["white", "black", "silver", "red"][idx - 1],
                "vehicle_type": vehicle_type,
                "dimensions": {"length_inches": 210 + idx * 12, "height_inches": 76, "wheelbase_inches": 144},
                "photo_file_ids": [files[(idx + 2) % len(files)]["id"]],
                "notes": "Development sample vehicle record.",
            })
            await self.upsert("wrap_vehicles", vehicle)
            order = orders[(idx + 2) % len(orders)]
            work = work_orders[(idx + 1) % len(work_orders)] if work_orders else None
            project = base_doc(self.tenant_id, "wrap-project", idx, self.now - timedelta(days=24 - idx))
            estimate = [285000, 86500, 540000, 320000][idx - 1]
            project.update({
                "customer_id": customer["id"],
                "vehicle_id": vehicle["id"],
                "quote_id": quotes[(idx + 2) % len(quotes)]["id"],
                "order_id": order["id"],
                "work_order_id": work["id"] if work else None,
                "project_name": f"{customer['company']} {make} {model} Wrap",
                "project_type": coverage,
                "status": status,
                "coverage_summary": f"{coverage.replace('_', ' ').title()} development sample.",
                "estimate_total_cents": estimate,
                "deposit_required_cents": int(estimate * 0.5),
                "material_estimate_cents": int(estimate * 0.32),
                "labor_estimate_cents": int(estimate * 0.38),
                "assigned_user_ids": [self.user_id],
                "due_at": iso(at_day(self.now, idx + 9)),
                "completed_at": iso(at_day(self.now, -2)) if status == "completed" else None,
                "notes": "Development sample Wrap Lab project connected to existing customer/order records.",
            })
            await self.upsert("wrap_projects", project)
            coverage_doc = base_doc(self.tenant_id, "wrap-coverage", idx, self.now - timedelta(days=20 - idx))
            coverage_doc.update({
                "project_id": project["id"],
                "coverage_level": coverage,
                "panels": [
                    {"panel": "driver side", "status": "designed" if status != "completed" else "quality_checked", "square_feet": 45},
                    {"panel": "passenger side", "status": "measured" if status == "design_in_progress" else "printed", "square_feet": 45},
                ],
                "total_square_feet": [96, 32, 210, 128][idx - 1],
                "waste_percent": 15,
                "status": "approved" if status in {"install_scheduled", "completed"} else "draft",
            })
            await self.upsert("wrap_coverage_plans", coverage_doc)
            inspection = base_doc(self.tenant_id, "wrap-inspection", idx, self.now - timedelta(days=18 - idx))
            inspection.update({
                "project_id": project["id"],
                "inspection_type": "pre_install",
                "status": "completed" if status in {"install_scheduled", "completed"} else "draft",
                "inspector_user_id": self.user_id,
                "damage_items": [{"type": "scratch", "panel": "rear bumper", "severity": "minor"}] if idx == 3 else [],
                "before_photo_file_ids": [files[(idx + 4) % len(files)]["id"]],
                "signed_at": iso(at_day(self.now, -3)) if status in {"install_scheduled", "completed"} else None,
            })
            await self.upsert("wrap_inspections", inspection)
            scene = base_doc(self.tenant_id, "wrap-scene", idx, self.now - timedelta(days=16 - idx))
            scene.update({
                "project_id": project["id"],
                "revision": 1,
                "status": "approved" if status in {"install_scheduled", "completed"} else ("proof_ready" if status == "proof_ready" else "in_progress"),
                "vehicle_template_key": f"{make.lower()}-{model.lower()}-{year}",
                "artboard": {"width": 1200, "height": 600},
                "layers": [{"type": "logo_asset", "label": "Customer logo"}, {"type": "panel_guide", "label": "Vehicle side guide"}],
                "original_asset_file_ids": [files[(idx + 5) % len(files)]["id"]],
                "preflight_results": {"dpi": "ok", "bleed": "needs_review" if idx == 1 else "ok"},
            })
            await self.upsert("wrap_design_scenes", scene)
            panel = base_doc(self.tenant_id, "wrap-panel-plan", idx, self.now - timedelta(days=14 - idx))
            panel.update({
                "project_id": project["id"],
                "revision": 1,
                "status": "ready_for_production" if status in {"install_scheduled", "completed"} else "draft",
                "panels": [{"name": "side A", "width_inches": 52, "height_inches": 96}, {"name": "side B", "width_inches": 52, "height_inches": 96}],
                "export_manifest": {"local_only": True},
                "material_usage_square_feet": [110, 42, 238, 144][idx - 1],
                "material_cost_cents": int(project["material_estimate_cents"]),
                "labor_cost_cents": int(project["labor_estimate_cents"]),
            })
            await self.upsert("wrap_panel_plans", panel)
            packet = base_doc(self.tenant_id, "wrap-packet", idx, self.now - timedelta(days=10 - idx))
            packet.update({
                "project_id": project["id"],
                "packet_type": "completion" if status == "completed" else "work_order",
                "revision": 1,
                "status": "signed" if status == "completed" else "generated",
                "snapshot": {"project_name": project["project_name"], "coverage": coverage},
                "generated_by_user_id": self.user_id,
                "sent_at": iso(at_day(self.now, -5)) if status == "completed" else None,
                "signed_at": iso(at_day(self.now, -2)) if status == "completed" else None,
            })
            await self.upsert("wrap_packets", packet)
            schedule = base_doc(self.tenant_id, "wrap-schedule", idx, self.now - timedelta(days=8 - idx))
            start = at_day(self.now, -1 if status == "completed" else 7 + idx, 9)
            schedule.update({
                "project_id": project["id"],
                "schedule_type": "install",
                "status": "completed" if status == "completed" else "scheduled",
                "title": f"{project['project_name']} install",
                "start_at": iso(start),
                "end_at": iso(start + timedelta(hours=6)),
                "assigned_user_ids": [self.user_id],
                "location": customer.get("installation_address", {}).get("line1"),
            })
            await self.upsert("wrap_schedules", schedule)
            warranty = base_doc(self.tenant_id, "wrap-warranty", idx, self.now - timedelta(days=5 - idx))
            warranty.update({
                "project_id": project["id"],
                "status": "active" if status == "completed" else "draft",
                "starts_at": iso(at_day(self.now, -2)) if status == "completed" else None,
                "expires_at": iso(at_day(self.now, 365)) if status == "completed" else None,
                "coverage_terms": ["Installation workmanship", "Laminate adhesion"],
                "care_instructions": ["Hand wash only for first 14 days", "Avoid pressure washing edges"],
                "warranty_value_cents": int(project["estimate_total_cents"] * 0.1),
            })
            await self.upsert("wrap_warranties", warranty)
            activity = base_doc(self.tenant_id, "wrap-activity", idx, self.now - timedelta(days=idx))
            activity.update({
                "project_id": project["id"],
                "actor_type": "staff",
                "actor_id": self.user_id,
                "actor_email": self.user["email"],
                "action": "project.sample_progress",
                "entity_type": "wrap_project",
                "entity_id": project["id"],
                "summary": f"Development sample Wrap Lab project moved to {status}.",
            })
            await self.upsert("wrap_activity_events", activity)

    async def seed_comms_and_activity(
        self,
        customers: list[dict[str, Any]],
        quotes: list[dict[str, Any]],
        orders: list[dict[str, Any]],
        work_orders: list[dict[str, Any]],
        invoices: list[dict[str, Any]],
        employees: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        webstores: list[dict[str, Any]],
    ) -> None:
        for idx in range(1, 13):
            order = orders[(idx - 1) % len(orders)]
            note = base_doc(self.tenant_id, "internal-note", idx, self.now - timedelta(days=idx))
            note.update({
                "title": "Development sample note",
                "body": "Customer prefers concise proofs and afternoon installation windows.",
                "author_user_id": self.user_id,
                "visibility": "internal",
                "customer_id": order["customer_id"],
                "order_id": order["id"],
                "work_order_id": work_orders[(idx - 1) % len(work_orders)]["id"] if work_orders else None,
                "pinned": idx in (2, 7),
            })
            await self.upsert("internal_notes", note)
        for idx in range(1, 7):
            order = orders[(idx - 1) % len(orders)]
            thread = base_doc(self.tenant_id, "message-thread", idx, self.now - timedelta(days=idx + 1))
            thread.update({
                "thread_type": "order_discussion",
                "title": f"{order['job_name']} coordination",
                "created_by_user_id": self.user_id,
                "participant_user_ids": [self.user_id],
                "participant_employee_ids": [employees[idx % len(employees)]["id"]],
                "customer_id": order["customer_id"],
                "order_id": order["id"],
                "visibility": "internal",
                "last_message_at": iso(self.now - timedelta(hours=idx)),
            })
            await self.upsert("message_threads", thread)
            for msg_idx, body in enumerate(["Proof is ready for review.", "Production will hold until artwork is approved."], start=1):
                msg = base_doc(self.tenant_id, "thread-message", f"{idx}-{msg_idx}", self.now - timedelta(days=idx, hours=msg_idx))
                msg.update({
                    "thread_id": thread["id"],
                    "sender_user_id": self.user_id if msg_idx == 1 else None,
                    "sender_employee_id": employees[idx % len(employees)]["id"] if msg_idx == 2 else None,
                    "body": body,
                    "message_type": "message",
                    "visibility": "internal",
                    "idempotency_key": seed_id("thread-message-key", f"{idx}-{msg_idx}"),
                })
                await self.upsert("thread_messages", msg)
        for idx, customer in enumerate(customers[:8], start=1):
            email = base_doc(self.tenant_id, "email-log", idx, self.now - timedelta(days=idx))
            email.update({
                "customer_id": customer["id"],
                "to_email": customer["email"],
                "from_email": "hello@example.signguy.dev",
                "subject": ["Quote follow-up", "Proof ready", "Invoice sent", "Install reminder"][idx % 4],
                "status": "sent",
                "direction": "outbound",
                "related_type": "quote" if idx % 2 else "order",
                "related_id": quotes[idx % len(quotes)]["id"] if idx % 2 else orders[idx % len(orders)]["id"],
                "body_preview": "Local development email history only. No message was sent.",
                "provider": "local_sample",
            })
            await self.upsert("email_logs", email)
        for idx in range(1, 11):
            notification = base_doc(self.tenant_id, "notification", idx, self.now - timedelta(hours=idx * 3))
            notification.update({
                "recipient_user_id": self.user_id,
                "title": ["Proof awaiting approval", "Invoice overdue", "Low inventory", "Install scheduled"][idx % 4],
                "body": "Development sample notification.",
                "status": "unread" if idx <= 6 else "read",
                "severity": "warning" if idx in (2, 6) else "info",
                "module": ["proofs", "finance", "inventory", "calendar"][idx % 4],
                "entity_type": "order",
                "entity_id": orders[idx % len(orders)]["id"],
            })
            await self.upsert("notifications", notification)
        for idx in range(1, 25):
            order = orders[(idx - 1) % len(orders)]
            activity = base_doc(self.tenant_id, "activity-event", idx, self.now - timedelta(days=idx % 15, hours=idx))
            activity.update({
                "module": ["sales", "production", "finance", "inventory", "webstores", "wrap_lab"][idx % 6],
                "action": ["created", "status_changed", "note_added", "payment_recorded"][idx % 4],
                "entity_type": "order",
                "entity_id": order["id"],
                "summary": f"Development sample activity for {order['job_name']}.",
                "severity": "warning" if idx in (5, 11, 18) else "info",
                "actor_user_id": self.user_id,
            })
            await self.upsert("activity_events", activity)
            audit = base_doc(self.tenant_id, "audit-event", idx, self.now - timedelta(days=idx % 18, minutes=idx))
            audit.update({
                "action": ["order.create", "quote.status_change", "invoice.payment_added", "work_order.stage_update"][idx % 4],
                "entity_type": ["order", "quote", "invoice", "work_order"][idx % 4],
                "entity_id": [order["id"], quotes[idx % len(quotes)]["id"], invoices[idx % len(invoices)]["id"], work_orders[idx % len(work_orders)]["id"]][idx % 4],
                "actor_user_id": self.user_id,
                "summary": "Development sample audit trail entry.",
                "metadata": {"seed_batch_id": SEED_BATCH_ID},
            })
            await self.upsert("audit_events", audit)
        for idx in range(1, 5):
            conversation = base_doc(self.tenant_id, "assistant-conversation", idx, self.now - timedelta(days=idx))
            conversation.update({
                "user_id": self.user_id,
                "mode": "business",
                "title": ["Daily priorities", "Production load", "Receivables", "Quote follow-ups"][idx - 1],
                "status": "active",
                "last_message_at": iso(self.now - timedelta(hours=idx)),
                "active_context": {"source_entity_type": "order", "source_entity_id": orders[idx]["id"]},
            })
            await self.upsert("assistant_conversations", conversation)
            message = base_doc(self.tenant_id, "assistant-message", idx, self.now - timedelta(hours=idx))
            message.update({
                "conversation_id": conversation["id"],
                "role": "assistant",
                "content": "Local sample assistant response. No AI provider call was made.",
                "created_by_user_id": self.user_id,
            })
            await self.upsert("assistant_messages", message)
            insight = base_doc(self.tenant_id, "assistant-insight", idx, self.now - timedelta(hours=idx + 1))
            insight.update({
                "insight_key": f"dev-sample-{idx}",
                "title": conversation["title"],
                "summary": "Development sample Business Assistant insight calculated from seeded records.",
                "status": "new",
                "source_citations": [{"source_type": "order", "source_id": orders[idx]["id"]}],
            })
            await self.upsert("assistant_insights", insight)


async def resolve_tenant(owner_email: str | None, tenant_slug: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if tenant_slug:
        tenant = await db.tenants.find_one({"slug": tenant_slug})
        if not tenant:
            raise RuntimeError(f"No tenant found for slug {tenant_slug!r}")
        user = await db.users.find_one({"tenant_id": tenant["id"], "email": owner_email}) if owner_email else await db.users.find_one({"tenant_id": tenant["id"], "is_active": True})
        if not user:
            raise RuntimeError(f"No active user found for tenant {tenant_slug!r}")
        return tenant, user
    email = (owner_email or DEFAULT_OWNER_EMAIL).lower().strip()
    users = await db.users.find({"email": email, "is_active": True}).to_list(length=10)
    if len(users) != 1:
        raise RuntimeError(f"Expected exactly one active user for {email!r}; found {len(users)}")
    user = users[0]
    tenant = await db.tenants.find_one({"id": user["tenant_id"]})
    if not tenant:
        raise RuntimeError(f"User {email!r} references missing tenant {user['tenant_id']!r}")
    return tenant, user


def require_development() -> None:
    settings = get_settings()
    db_name = settings.db_name.lower()
    if settings.env != "development":
        raise RuntimeError(f"Refusing to run sample data outside ENV=development (current ENV={settings.env!r})")
    if any(marker in db_name for marker in ("prod", "production")):
        raise RuntimeError(f"Refusing to run sample data against production-looking DB_NAME={settings.db_name!r}")


async def cleanup(tenant_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for collection in CLEANUP_COLLECTIONS:
        result = await db[collection].delete_many({
            "tenant_id": tenant_id,
            "seed_batch_id": SEED_BATCH_ID,
            "is_dev_sample_data": True,
        })
        counts[collection] = result.deleted_count
    return {k: v for k, v in sorted(counts.items()) if v}


async def summary(tenant_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for collection in reversed(CLEANUP_COLLECTIONS):
        counts[collection] = await db[collection].count_documents({
            "tenant_id": tenant_id,
            "seed_batch_id": SEED_BATCH_ID,
            "is_dev_sample_data": True,
        })
    return {k: v for k, v in sorted(counts.items()) if v}


def print_counts(title: str, counts: dict[str, int]) -> None:
    print(title)
    for key, value in sorted(counts.items()):
        print(f"  {key}: {value}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed or cleanup local development sample data.")
    parser.add_argument("command", choices=["seed", "cleanup", "summary"])
    parser.add_argument("--owner-email", default=DEFAULT_OWNER_EMAIL)
    parser.add_argument("--tenant-slug", default=None)
    args = parser.parse_args()

    require_development()
    await ensure_indexes()
    tenant, user = await resolve_tenant(args.owner_email, args.tenant_slug)

    print(f"Target tenant: {tenant.get('name')} ({tenant.get('slug') or tenant.get('id')})")
    print(f"Target user: {user.get('email')}")
    print(f"Seed batch: {SEED_BATCH_ID}")

    if args.command == "cleanup":
        counts = await cleanup(tenant["id"])
        print_counts("Deleted development sample records:", counts)
        return 0
    if args.command == "summary":
        counts = await summary(tenant["id"])
        print_counts("Current development sample records:", counts)
        return 0

    seeder = Seeder(tenant, user)
    counts = await seeder.seed_all()
    print_counts("Seeded or refreshed development sample records:", counts)
    final_counts = await summary(tenant["id"])
    print_counts("Current development sample records:", final_counts)
    return 0


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))

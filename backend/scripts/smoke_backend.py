"""End-to-end backend smoke test (run via: python -m tests._test_env run -- python scripts/smoke_backend.py)

End-to-end backend smoke test covering the full Acceptance Criteria workflow.

Register two tenants -> verify isolation.
Tenant A: register owner -> create customer -> create quote -> convert-to-order (twice, expect idempotent)
         -> add order items -> create work order -> create invoice (twice, idempotent)
         -> record two partial payments -> send email (fails gracefully) -> upload+attach a doc.
Tenant B: try to fetch tenant A's records by id -> expect 404s.
"""
from __future__ import annotations

import io
import os
import sys
import time
import uuid

import requests

_BACKEND = str(__import__("pathlib").Path(__file__).resolve().parents[1])
sys.path.insert(0, _BACKEND)
from app.core.test_isolation import require_isolated_script_target  # noqa: E402

_ROOT = os.environ.get("SIGNGUY_TEST_API_BASE_URL", "").rstrip("/")
require_isolated_script_target(os.environ, _ROOT)  # exits before any write if not a disposable target
BASE = _ROOT + "/api"


def _post(path, json=None, token=None, files=None, data=None, headers=None):
    h = dict(headers or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{BASE}{path}", json=json, files=files, data=data, headers=h, timeout=30)
    return r


def _get(path, token=None, params=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{BASE}{path}", headers=h, params=params, timeout=30)


def _patch(path, json, token):
    return requests.patch(f"{BASE}{path}", json=json, headers={"Authorization": f"Bearer {token}"}, timeout=30)


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        sys.exit(1)


def main() -> int:
    slug_a = f"acme-{uuid.uuid4().hex[:6]}"
    slug_b = f"other-{uuid.uuid4().hex[:6]}"

    # Register tenant A
    r = _post("/auth/register-tenant", json={
        "tenant_name": "Acme Signs", "tenant_slug": slug_a,
        "owner_email": f"owner-{slug_a}@example.com", "owner_full_name": "Ann Owner",
        "owner_password": "hunter2hunter2",
    })
    check(r.status_code == 201, f"register tenant A: {r.status_code}")
    tokA = r.json()["access_token"]
    userA = r.json()["user"]
    permsA = r.json()["permissions"]
    check("customer:write" in permsA and "invoice:write" in permsA, "owner has permissions")

    # Register tenant B
    r = _post("/auth/register-tenant", json={
        "tenant_name": "Other Shop", "tenant_slug": slug_b,
        "owner_email": f"owner-{slug_b}@example.com", "owner_full_name": "Bob Boss",
        "owner_password": "hunter2hunter2",
    })
    check(r.status_code == 201, "register tenant B")
    tokB = r.json()["access_token"]

    # /auth/me works
    me = _get("/auth/me", token=tokA)
    check(me.status_code == 200 and me.json()["user"]["email"].endswith(f"{slug_a}@example.com"), "auth me")

    # Create customer
    r = _post("/customers", json={"name": "Diner Deluxe", "email": "diner@example.com", "phone": "555-0100"}, token=tokA)
    check(r.status_code == 201, f"create customer: {r.status_code}")
    cust_id = r.json()["id"]

    # Create quote
    r = _post("/quotes", json={"customer_id": cust_id, "job_name": "Storefront LED", "total_cents": 250000, "notes": "Rush"}, token=tokA)
    check(r.status_code == 201, f"create quote: {r.status_code}")
    quote = r.json()
    check(quote["number"] >= 1 and quote["total_cents"] == 250000, "quote number and total")

    # Send status update
    r = _post(f"/quotes/{quote['id']}/status", json={"status": "sent"}, token=tokA)
    check(r.status_code == 200 and r.json()["status"] == "sent", "quote sent")
    _post(f"/quotes/{quote['id']}/status", json={"status": "approved"}, token=tokA)

    # Convert quote twice - must be idempotent
    r1 = _post(f"/quotes/{quote['id']}/convert-to-order", token=tokA)
    check(r1.status_code == 200, "first convert-to-order")
    order_id_1 = r1.json()["order"]["id"]
    r2 = _post(f"/quotes/{quote['id']}/convert-to-order", token=tokA)
    check(r2.status_code == 200, "second convert-to-order")
    order_id_2 = r2.json()["order"]["id"]
    check(order_id_1 == order_id_2, f"idempotent convert: {order_id_1} == {order_id_2}")
    check(r2.json()["already_converted"] is True, "already_converted flag")

    # Add order items
    r = _post(f"/orders/{order_id_1}/items", json={"description": "LED Channel Letters", "quantity": 1, "unit_price_cents": 200000}, token=tokA)
    check(r.status_code == 201, "add item 1")
    item1 = r.json()
    r = _post(f"/orders/{order_id_1}/items", json={"description": "Installation", "quantity": 4, "unit_price_cents": 12500}, token=tokA)
    check(r.status_code == 201, "add item 2")

    # Confirm order status
    r = _post(f"/orders/{order_id_1}/status", json={"status": "confirmed"}, token=tokA)
    check(r.status_code == 200 and r.json()["status"] == "confirmed", "order confirmed")

    # Fetch order detail
    r = _get(f"/orders/{order_id_1}", token=tokA)
    check(r.status_code == 200 and r.json()["totals"]["item_count"] == 2, "order items in totals")
    check(r.json()["totals"]["subtotal_cents"] == 200000 + 4*12500, "subtotal correct")

    # Create work order (multiple allowed)
    r = _post("/work-orders", json={"order_id": order_id_1, "production_instructions": "Match Pantone 021 C"}, token=tokA)
    check(r.status_code == 201, "work order 1")
    wo_id = r.json()["id"]
    check(len(r.json()["items_snapshot"]) == 2, "items_snapshot has 2 items")
    r = _post("/work-orders", json={"order_id": order_id_1, "production_instructions": "Second panel"}, token=tokA)
    check(r.status_code == 201, "work order 2 (multiple allowed)")
    _post(f"/work-orders/{wo_id}/production-status", json={"production_status": "in_progress"}, token=tokA)

    # Create invoice - twice to test idempotency
    r = _post("/invoices", json={"order_id": order_id_1, "title": "Storefront LED", "total_cents": 250000, "due_date": "2026-02-01"}, token=tokA)
    check(r.status_code == 201, "first create invoice")
    inv_id = r.json()["invoice"]["id"]
    r2 = _post("/invoices", json={"order_id": order_id_1, "title": "Attempt dup", "total_cents": 999999}, token=tokA)
    check(r2.status_code == 201 and r2.json()["already_exists"] is True, "second create invoice = already_exists")
    check(r2.json()["invoice"]["id"] == inv_id, "same invoice id returned")

    # Record payments (partial)
    r = _post(f"/invoices/{inv_id}/payments", json={"amount_cents": 100000, "method": "check", "paid_on": "2026-01-15"}, token=tokA, headers={"Idempotency-Key": "pay-1"})
    check(r.status_code == 201, "first payment")
    r_dup = _post(f"/invoices/{inv_id}/payments", json={"amount_cents": 100000, "method": "check", "paid_on": "2026-01-15"}, token=tokA, headers={"Idempotency-Key": "pay-1"})
    check(r_dup.status_code == 201 and r_dup.json()["already_exists"] is True, "duplicate payment idempotent")

    r = _post(f"/invoices/{inv_id}/payments", json={"amount_cents": 150000, "method": "card", "paid_on": "2026-01-20"}, token=tokA, headers={"Idempotency-Key": "pay-2"})
    check(r.status_code == 201, "second payment (paid in full)")
    check(r.json()["invoice_status"] == "paid", f"invoice status paid, got {r.json()['invoice_status']}")

    r = _get(f"/invoices/{inv_id}", token=tokA)
    check(r.json()["invoice"]["paid_cents"] == 250000 and r.json()["invoice"]["balance_due_cents"] == 0, "balance is zero")

    # Send an email (SendGrid not configured => logged as failed but non-crashing)
    r = _post("/emails/send", json={
        "to_email": "diner@example.com", "subject": "Invoice", "body": "Here's your invoice.",
        "template": "invoice_sent", "customer_id": cust_id, "related_type": "invoice", "related_id": inv_id,
    }, token=tokA)
    check(r.status_code == 201, f"email send request accepted: {r.status_code}")
    check(r.json()["email"]["status"] in ("failed", "sent", "skipped"), "email log has final status")

    # Upload a file with parent attachment
    files = {"file": ("proof.txt", io.BytesIO(b"proof contents"), "text/plain")}
    data = {"visibility": "internal", "parent_type": "order", "parent_id": order_id_1}
    r = _post("/files/upload", files=files, data=data, token=tokA)
    check(r.status_code == 201, f"file upload: {r.status_code} {r.text[:200]}")
    file_id = r.json()["file"]["id"]

    # Download the file (must be authenticated)
    r = _get(f"/files/{file_id}/download", token=tokA)
    check(r.status_code == 200 and r.content == b"proof contents", "download roundtrip")

    # Cross-tenant checks: tenant B cannot see tenant A records
    r = _get(f"/customers/{cust_id}", token=tokB)
    check(r.status_code == 404, "tenant B cannot fetch tenant A customer")
    r = _get(f"/orders/{order_id_1}", token=tokB)
    check(r.status_code == 404, "tenant B cannot fetch tenant A order")
    r = _get(f"/invoices/{inv_id}", token=tokB)
    check(r.status_code == 404, "tenant B cannot fetch tenant A invoice")
    r = _get(f"/files/{file_id}/download", token=tokB)
    check(r.status_code == 404, "tenant B cannot download tenant A file")

    # Unauthenticated cannot download file
    r = requests.get(f"{BASE}/files/{file_id}/download", timeout=10)
    check(r.status_code == 401, f"unauth download blocked: {r.status_code}")

    # Dashboard
    r = _get("/dashboard/summary", token=tokA)
    check(r.status_code == 200, "dashboard summary")
    d = r.json()
    check(d["counts"]["active_orders"] >= 1, "dashboard active_orders >= 1")

    # Audit trail
    r = _get("/audit", token=tokA, params={"entity_type": "order", "entity_id": order_id_1})
    check(r.status_code == 200 and r.json()["total"] >= 4, f"audit trail has events: {r.json().get('total')}")

    print("\nSMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

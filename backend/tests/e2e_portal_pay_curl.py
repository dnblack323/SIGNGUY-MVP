"""End-to-end curl-style verification against the LIVE public preview.

Uses AUTH_DEV_BYPASS to obtain a staff token, seeds a portal identity via the
staff endpoint, mints a portal JWT locally (same JWT secret as backend),
then exercises:
  - portal auth separation (staff↔portal cross-rejection)
  - portal invoice list scope + non-draft filter
  - stripe-intent initiate (reuse) + dev-simulate-confirm + replay idempotency
  - portal detail shows balance=0 + financial_status=paid
  - void / paid / overpayment / cross-customer safety guards
  - portal messages excludes provider IDs
  - public introspect requires ?t=

Run: python /app/backend/tests/e2e_portal_pay_curl.py
"""
from __future__ import annotations
import os, sys, uuid, json
sys.path.insert(0, "/app/backend")

import requests
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

def _step(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _step.failed += 1
_step.failed = 0

# --- Load env for JWT + Mongo -------------------------------------------------

from app.core.portal_security import create_portal_token  # noqa: E402

# --- Staff dev-login ----------------------------------------------------------
r = requests.post(f"{BASE}/api/auth/dev-login", timeout=15)
_step("staff dev-login", r.status_code == 200, r.text[:200])
staff_token = r.json()["access_token"]
staff_tenant = r.json()["user"]["tenant_id"]
SH = {"Authorization": f"Bearer {staff_token}"}

# --- Seed: customers + invoices via staff API --------------------------------
cust_a = requests.post(f"{BASE}/api/customers", headers=SH,
                      json={"name": f"E2E A {uuid.uuid4().hex[:5]}", "email": f"a-{uuid.uuid4().hex[:5]}@ex.com"}).json()
cust_b = requests.post(f"{BASE}/api/customers", headers=SH,
                      json={"name": f"E2E B {uuid.uuid4().hex[:5]}", "email": f"b-{uuid.uuid4().hex[:5]}@ex.com"}).json()
_step("create customers", "id" in cust_a and "id" in cust_b, f"a={cust_a.get('id')} b={cust_b.get('id')}")

# Seed invoices directly in Mongo to avoid full quote→order→invoice pipeline
import asyncio
from app.core.db import db

async def _seed():
    common = {"total_cents": 10000, "amount_paid_cents": 0, "amount_refunded_cents": 0,
              "balance_due_cents": 10000, "document_status": "issued", "financial_status": "unpaid",
              "title": "E2E Signage", "created_at": "2026-02-01T00:00:00+00:00",
              "updated_at": "2026-02-01T00:00:00+00:00"}
    inv_a = f"inv-e2e-{uuid.uuid4().hex[:6]}"
    inv_b = f"inv-e2e-{uuid.uuid4().hex[:6]}"
    inv_void = f"inv-e2e-{uuid.uuid4().hex[:6]}"
    inv_paid = f"inv-e2e-{uuid.uuid4().hex[:6]}"
    inv_draft = f"inv-e2e-{uuid.uuid4().hex[:6]}"
    n1 = 900000 + int(uuid.uuid4().int % 90000)
    order_id_a = f"o-e2e-{uuid.uuid4().hex[:6]}"
    await db.invoices.insert_many([
        {"id": inv_a, "tenant_id": staff_tenant, "customer_id": cust_a["id"], "order_id": order_id_a, "number": n1, **common},
        {"id": inv_b, "tenant_id": staff_tenant, "customer_id": cust_b["id"], "order_id": f"o-{uuid.uuid4().hex[:6]}", "number": n1+1, **common},
        {"id": inv_void, "tenant_id": staff_tenant, "customer_id": cust_a["id"], "order_id": f"o-{uuid.uuid4().hex[:6]}", "number": n1+2, **{**common, "document_status": "void"}},
        {"id": inv_paid, "tenant_id": staff_tenant, "customer_id": cust_a["id"], "order_id": f"o-{uuid.uuid4().hex[:6]}", "number": n1+3, **{**common, "amount_paid_cents": 10000, "balance_due_cents": 0, "financial_status": "paid"}},
        {"id": inv_draft, "tenant_id": staff_tenant, "customer_id": cust_a["id"], "order_id": f"o-{uuid.uuid4().hex[:6]}", "number": n1+4, **{**common, "document_status": "draft"}},
    ])
    await db.payments.insert_one({
        "id": f"pay-e2e-{uuid.uuid4().hex[:6]}", "tenant_id": staff_tenant, "invoice_id": inv_paid,
        "customer_id": cust_a["id"], "source": "manual", "status": "confirmed",
        "amount_cents": 10000, "method": "cash", "paid_on": "2026-02-01",
        "created_at": "2026-02-01T00:00:00+00:00", "updated_at": "2026-02-01T00:00:00+00:00",
    })
    return inv_a, inv_b, inv_void, inv_paid, inv_draft

inv_a, inv_b, inv_void, inv_paid, inv_draft = asyncio.run(_seed())
_step("seed invoices in mongo", True, f"a={inv_a} b={inv_b} void={inv_void} paid={inv_paid} draft={inv_draft}")

# --- Create portal identities via staff endpoint -----------------------------
pi_a = requests.post(f"{BASE}/api/portal-identities", headers=SH, json={
    "customer_id": cust_a["id"], "email": f"pi-a-{uuid.uuid4().hex[:5]}@ex.com",
    "permissions_preset": "owner_full", "send_invite_email": False,
}).json()
_step("create portal identity owner_full", "id" in pi_a, str(pi_a)[:200])

pi_viewer = requests.post(f"{BASE}/api/portal-identities", headers=SH, json={
    "customer_id": cust_a["id"], "email": f"pi-v-{uuid.uuid4().hex[:5]}@ex.com",
    "permissions_preset": "viewer_only", "send_invite_email": False,
}).json()
_step("create portal identity viewer_only", "id" in pi_viewer)

# --- Mint portal JWTs directly (same JWT_SECRET as backend) ------------------
token_a = create_portal_token(portal_identity_id=pi_a["id"], tenant_id=staff_tenant, customer_id=cust_a["id"])
token_v = create_portal_token(portal_identity_id=pi_viewer["id"], tenant_id=staff_tenant, customer_id=cust_a["id"])
PH = {"Authorization": f"Bearer {token_a}"}
VH = {"Authorization": f"Bearer {token_v}"}
_step("mint portal JWTs", bool(token_a) and bool(token_v))

# --- Portal auth separation ---------------------------------------------------
r = requests.get(f"{BASE}/api/portal/auth/me", headers=SH)
_step("staff token rejected by /api/portal/auth/me", r.status_code == 401, f"got {r.status_code} {r.text[:150]}")

r = requests.get(f"{BASE}/api/customers", headers=PH)
_step("portal token rejected by /api/customers", r.status_code == 401, f"got {r.status_code} {r.text[:150]}")

r = requests.get(f"{BASE}/api/portal/auth/me", headers=PH)
_step("portal /auth/me returns identity", r.status_code == 200 and r.json().get("identity", {}).get("id") == pi_a["id"], str(r.json())[:200])

# --- Portal invoice list scope + draft filter --------------------------------
r = requests.get(f"{BASE}/api/portal/invoices", headers=PH)
ok = r.status_code == 200
ids = [x["id"] for x in r.json().get("items", [])] if ok else []
_step("portal invoices lists non-draft only for own customer",
      ok and inv_a in ids and inv_paid in ids and inv_void in ids and inv_draft not in ids and inv_b not in ids,
      f"ids={ids}")

# --- Stripe intent initiate + reuse ------------------------------------------
r = requests.post(f"{BASE}/api/portal/invoices/{inv_a}/stripe-intents", headers=PH, json={"amount_cents": 10000})
_step("initiate stripe intent (201)", r.status_code == 201, r.text[:300])
body = r.json()
payment_id = body.get("payment_id")
client_secret = body.get("client_secret")
pk = body.get("publishable_key")
_step("client_secret + publishable_key in response body", bool(client_secret) and bool(pk),
      f"cs={client_secret and client_secret[:20]}... pk={pk and pk[:20]}...")

r2 = requests.post(f"{BASE}/api/portal/invoices/{inv_a}/stripe-intents", headers=PH, json={"amount_cents": 10000})
_step("reuse existing pending payment (already_exists=true)",
      r2.status_code == 201 and r2.json().get("payment_id") == payment_id and r2.json().get("already_exists") is True,
      str(r2.json())[:200])

# --- Overpayment blocked ------------------------------------------------------
r = requests.post(f"{BASE}/api/portal/invoices/{inv_a}/stripe-intents", headers=PH, json={"amount_cents": 999999})
_step("overpayment blocked (400)", r.status_code == 400 and "exceeds" in r.text.lower(), r.text[:200])

# --- Void invoice blocked -----------------------------------------------------
r = requests.post(f"{BASE}/api/portal/invoices/{inv_void}/stripe-intents", headers=PH, json={"amount_cents": 100})
_step("void invoice blocked (400)", r.status_code == 400 and "void" in r.text.lower(), r.text[:200])

# --- Fully-paid blocked -------------------------------------------------------
r = requests.post(f"{BASE}/api/portal/invoices/{inv_paid}/stripe-intents", headers=PH, json={"amount_cents": 100})
_step("fully-paid invoice blocked (400)", r.status_code == 400 and "exceeds" in r.text.lower(), r.text[:200])

# --- Cross-customer 404 -------------------------------------------------------
r = requests.post(f"{BASE}/api/portal/invoices/{inv_b}/stripe-intents", headers=PH, json={"amount_cents": 100})
_step("cross-customer invoice returns 404", r.status_code == 404, r.text[:200])

# --- Viewer permission gate ---------------------------------------------------
r = requests.post(f"{BASE}/api/portal/invoices/{inv_a}/stripe-intents", headers=VH, json={"amount_cents": 100})
_step("viewer_only cannot initiate (403)", r.status_code == 403, r.text[:200])

# --- Dev-simulate-confirm (EC4 webhook path) ---------------------------------
r = requests.post(f"{BASE}/api/portal/payments/{payment_id}/dev-simulate-confirm", headers=PH)
_step("dev-simulate-confirm 200", r.status_code == 200, r.text[:200])

# Refetch invoice detail
r = requests.get(f"{BASE}/api/portal/invoices/{inv_a}", headers=PH)
ok = r.status_code == 200
inv = r.json().get("invoice", {}) if ok else {}
pays = r.json().get("payments", []) if ok else []
_step("post-confirm: balance=0 + financial_status=paid + payment row present",
      inv.get("balance_due_cents") == 0 and inv.get("financial_status") == "paid"
      and any(p["id"] == payment_id and p["status"] == "confirmed" for p in pays),
      f"balance={inv.get('balance_due_cents')} status={inv.get('financial_status')} payments={[p['id'] for p in pays]}")

# --- Replay idempotency -------------------------------------------------------
r = requests.post(f"{BASE}/api/portal/payments/{payment_id}/dev-simulate-confirm", headers=PH)
_step("replay confirm returns already_confirmed=true",
      r.status_code == 200 and r.json().get("already_confirmed") is True, r.text[:200])

# No duplicate payment row (use pymongo sync to avoid motor loop reuse issues)
from pymongo import MongoClient
_pm = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
_step("only one payment row for inv_a after replay",
      _pm.payments.count_documents({"tenant_id": staff_tenant, "invoice_id": inv_a}) == 1)

# --- Portal messages excludes provider IDs -----------------------------------
r = requests.get(f"{BASE}/api/portal/messages", headers=PH)
ok = r.status_code == 200
_step("portal messages returns 200", ok, r.text[:200])
if ok:
    items = r.json().get("items", [])
    leak = any(("sendgrid_message_id" in it) or ("provider_message_id" in it) or ("error" in it and it.get("error")) for it in items)
    _step("portal messages excludes provider IDs / error diagnostics", not leak)

# --- Public introspect requires ?t= ------------------------------------------
r = requests.get(f"{BASE}/api/public/token/introspect")
_step("public introspect without ?t= returns 4xx", r.status_code in (400, 422), f"{r.status_code} {r.text[:150]}")

# --- Magic-link never reveals identity existence -----------------------------
r = requests.post(f"{BASE}/api/portal/auth/magic-link", json={"email": f"nobody-{uuid.uuid4().hex[:6]}@ex.com", "tenant_slug": staff_tenant})
_step("magic-link for unknown email still returns status:sent",
      r.status_code == 200 and r.json().get("status") == "sent", str(r.json())[:200])

# --- Magic-link verify with bad token returns 401 ----------------------------
r = requests.post(f"{BASE}/api/portal/auth/magic-link/verify", json={"token": "not-a-real-token"})
_step("magic-link verify with invalid token returns 401", r.status_code == 401, r.text[:200])

# --- Cleanup (pymongo sync) ---------------------------------------------------
_pm.invoices.delete_many({"id": {"$in": [inv_a, inv_b, inv_void, inv_paid, inv_draft]}})
_pm.payments.delete_many({"tenant_id": staff_tenant, "invoice_id": {"$in": [inv_a, inv_paid]}})
_pm.customers.delete_many({"id": {"$in": [cust_a["id"], cust_b["id"]]}})
_pm.portal_identities.delete_many({"id": {"$in": [pi_a["id"], pi_viewer["id"]]}})

print(f"\n=== FAILURES: {_step.failed} ===")
sys.exit(1 if _step.failed else 0)

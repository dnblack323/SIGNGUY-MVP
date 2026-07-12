"""Seed portal identity + invoices; write JSON so Playwright can read the token."""
import os, sys, uuid, json, asyncio
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env"); load_dotenv("/app/backend/.env")
import requests
from pymongo import MongoClient
from app.core.portal_security import create_portal_token

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
r = requests.post(f"{BASE}/api/auth/dev-login", timeout=15).json()
staff_token = r["access_token"]; tenant = r["user"]["tenant_id"]
SH = {"Authorization": f"Bearer {staff_token}"}

cust = requests.post(f"{BASE}/api/customers", headers=SH,
                    json={"name": f"UI E2E {uuid.uuid4().hex[:5]}", "email": f"ui-{uuid.uuid4().hex[:5]}@ex.com"}).json()

pm = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
inv_id = f"inv-ui-{uuid.uuid4().hex[:6]}"
inv_paid = f"inv-uip-{uuid.uuid4().hex[:6]}"
inv_void = f"inv-uiv-{uuid.uuid4().hex[:6]}"
n = 800000 + int(uuid.uuid4().int % 90000)
common = {"total_cents": 25000, "amount_paid_cents": 0, "amount_refunded_cents": 0,
          "balance_due_cents": 25000, "document_status": "issued", "financial_status": "unpaid",
          "title": "UI Signage", "created_at": "2026-02-01T00:00:00+00:00",
          "updated_at": "2026-02-01T00:00:00+00:00"}
pm.invoices.insert_many([
    {"id": inv_id, "tenant_id": tenant, "customer_id": cust["id"], "order_id": f"o-{uuid.uuid4().hex[:6]}", "number": n, **common},
    {"id": inv_paid, "tenant_id": tenant, "customer_id": cust["id"], "order_id": f"o-{uuid.uuid4().hex[:6]}", "number": n+1,
     **{**common, "amount_paid_cents": 25000, "balance_due_cents": 0, "financial_status": "paid"}},
    {"id": inv_void, "tenant_id": tenant, "customer_id": cust["id"], "order_id": f"o-{uuid.uuid4().hex[:6]}", "number": n+2,
     **{**common, "document_status": "void"}},
])
pm.payments.insert_one({
    "id": f"pay-ui-{uuid.uuid4().hex[:6]}", "tenant_id": tenant, "invoice_id": inv_paid,
    "customer_id": cust["id"], "source": "manual", "status": "confirmed",
    "amount_cents": 25000, "method": "cash", "paid_on": "2026-02-01",
    "created_at": "2026-02-01T00:00:00+00:00", "updated_at": "2026-02-01T00:00:00+00:00",
})

pi = requests.post(f"{BASE}/api/portal-identities", headers=SH, json={
    "customer_id": cust["id"], "email": f"pi-ui-{uuid.uuid4().hex[:5]}@ex.com",
    "permissions_preset": "owner_full", "send_invite_email": False,
}).json()
token = create_portal_token(portal_identity_id=pi["id"], tenant_id=tenant, customer_id=cust["id"])

out = {"base": BASE, "tenant": tenant, "token": token, "identity_id": pi["id"],
       "customer_id": cust["id"], "invoice_id": inv_id, "inv_paid": inv_paid, "inv_void": inv_void}
open("/tmp/portal_ui_ctx.json", "w").write(json.dumps(out))
print(json.dumps(out, indent=2))

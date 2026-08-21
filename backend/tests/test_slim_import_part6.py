from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from httpx import ASGITransport, AsyncClient

from app.deps import get_current_user
from server import app


PASSPHRASE = "correct horse battery staple"
SIGNATURE = "SIGNGUY-SLIM-BACKUP"


def _json_bytes(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _data_file(path: str, value):
    data = _json_bytes(value)
    return {"path": path, "media_type": "application/json", "size_bytes": len(data), "sha256": _sha(data)}


def _encrypt_payload(payload: dict, passphrase: str = PASSPHRASE) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    aad = {
        "signature": SIGNATURE,
        "container_version": "1.0.0",
        "algorithm": "AES-256-GCM",
        "kdf": "PBKDF2-HMAC-SHA256",
        "kdf_iterations": 310000,
    }
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 310000, 32)
    encrypted = AESGCM(key).encrypt(nonce, _json_bytes(payload), _json_bytes(aad))
    return _json_bytes({
        **aad,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "tag_b64": base64.b64encode(encrypted[-16:]).decode("ascii"),
        "ciphertext_b64": base64.b64encode(encrypted[:-16]).decode("ascii"),
    })


def _backup_bytes(target_email: str) -> bytes:
    source_tenant = f"slim-tenant-{uuid.uuid4().hex[:8]}"
    now = "2026-08-21T12:00:00.000Z"
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    data = {
        "tenants": [{
            "id": source_tenant,
            "portable_id": "sgp_v1_tenant_source",
            "tenant_id": source_tenant,
            "company_name": "Slim Source Shop",
            "contact_email": "shop@example.com",
            "sales_tax_rate_basis_points": 725,
            "shop_timezone": "America/New_York",
        }],
        "users": [{
            "id": "su_1",
            "portable_id": "sgp_v1_user_1",
            "tenant_id": source_tenant,
            "display_name": "Slim Owner",
            "email_label": target_email,
            "is_active": True,
        }],
        "customers": [{
            "id": "sc_1",
            "portable_id": "sgp_v1_customer_1",
            "tenant_id": source_tenant,
            "customer_number": "C-7",
            "contact_name": "Ada Customer",
            "business_name": "Ada Signs",
            "email": "ada@example.com",
            "phone": "555-0101",
            "billing_line1": "100 Main",
            "billing_city": "Buffalo",
            "billing_state": "NY",
            "billing_postal_code": "14201",
            "billing_country": "US",
            "active": True,
            "tax_exempt": False,
            "internal_notes": "Imported note",
            "created_at": now,
            "updated_at": now,
        }],
        "estimates": [{
            "id": "se_1",
            "portable_id": "sgp_v1_estimate_1",
            "tenant_id": source_tenant,
            "customer_id": "sc_1",
            "estimate_number": "E-8",
            "document_date": "2026-08-20",
            "expires_at": "2026-09-20",
            "follow_up_at": None,
            "status": "converted",
            "subtotal_cents": 10000,
            "discount_cents": 0,
            "tax_cents": 725,
            "total_cents": 10725,
            "internal_notes": "Estimate note",
            "converted_order_id": "so_1",
            "created_at": now,
            "updated_at": now,
        }],
        "estimate_items": [{
            "id": "sei_1",
            "portable_id": "sgp_v1_estimate_item_1",
            "tenant_id": source_tenant,
            "estimate_id": "se_1",
            "position": 0,
            "description": "Window lettering",
            "quantity_decimal": "2",
            "unit_price_cents": 5000,
            "line_total_cents": 10000,
            "taxable": True,
            "production_required": True,
            "due_date": "2026-08-25",
            "assigned_user_id": "su_1",
            "internal_note": "Line note",
            "created_at": now,
            "updated_at": now,
        }],
        "orders": [{
            "id": "so_1",
            "portable_id": "sgp_v1_order_1",
            "tenant_id": source_tenant,
            "customer_id": "sc_1",
            "source_estimate_id": "se_1",
            "order_number": "O-9",
            "document_date": "2026-08-21",
            "due_date": "2026-08-28",
            "status": "in_production",
            "subtotal_cents": 10000,
            "discount_cents": 0,
            "tax_cents": 725,
            "total_cents": 10725,
            "internal_notes": "Order note",
            "created_at": now,
            "updated_at": now,
        }],
        "order_items": [{
            "id": "soi_1",
            "portable_id": "sgp_v1_order_item_1",
            "tenant_id": source_tenant,
            "order_id": "so_1",
            "source_estimate_item_id": "sei_1",
            "position": 0,
            "description": "Window lettering",
            "quantity_decimal": "2",
            "unit_price_cents": 5000,
            "line_total_cents": 10000,
            "taxable": True,
            "production_required": True,
            "production_stage": "in_progress",
            "completed": False,
            "due_date": "2026-08-25",
            "assigned_user_id": "su_1",
            "internal_note": "Order item note",
            "created_at": now,
            "updated_at": now,
        }],
        "invoices": [{
            "id": "si_1",
            "portable_id": "sgp_v1_invoice_1",
            "tenant_id": source_tenant,
            "order_id": "so_1",
            "customer_id": "sc_1",
            "invoice_number": "I-10",
            "document_date": "2026-08-21",
            "due_date": "2026-09-01",
            "document_status": "issued",
            "payment_status": "partial",
            "subtotal_cents": 10000,
            "discount_cents": 0,
            "tax_cents": 725,
            "total_cents": 10725,
            "amount_paid_cents": 5000,
            "balance_due_cents": 5725,
            "historical_amount_paid_note": "Manual Slim paid amount",
            "created_at": now,
            "updated_at": now,
        }],
        "calendar_events": [{
            "id": "sce_1",
            "portable_id": "sgp_v1_calendar_event_1",
            "tenant_id": source_tenant,
            "title": "Install",
            "order_id": "so_1",
            "order_item_id": "soi_1",
            "start_at": "2026-08-27T13:00:00.000Z",
            "end_at": "2026-08-27T15:00:00.000Z",
            "all_day": False,
            "assigned_user_id": "su_1",
            "created_by_user_id": "su_1",
            "status": "completed",
            "internal_note": "Calendar note",
            "created_at": now,
            "updated_at": now,
        }],
        "tenant_sequences": [],
        "reminders": [],
        "notes": [],
        "audit_events": [],
    }
    attachment = {
        "metadata": {
            "id": "sa_1",
            "portable_id": "sgp_v1_attachment_1",
            "tenant_id": source_tenant,
            "order_id": "so_1",
            "original_filename": "proof.pdf",
            "mime_type": "application/pdf",
            "byte_size": len(pdf),
            "sha256": _sha(pdf),
            "created_at": now,
        },
        "logical_path": "attachments/sgp_v1_attachment_1-proof.pdf",
        "content_base64": base64.b64encode(pdf).decode("ascii"),
    }
    data_inventory = [_data_file(f"data/{section}.json", data[section]) for section in data]
    attachment_inventory = [{
        "path": attachment["logical_path"],
        "content_type": "application/pdf",
        "size_bytes": len(pdf),
        "sha256": _sha(pdf),
        "source_portable_id": "sgp_v1_attachment_1",
    }]
    manifest = {
        "backup_id": f"sgp_v1_backup_{uuid.uuid4()}",
        "backup_format_version": "signguy-slim-backup-v1",
        "portable_contract_version": "1.0.0",
        "source_product": "SIGNGUY-SLIM",
        "source_application_version": "0.1.0-v1-part5",
        "source_commit": "43e32299f2e559b748b454d7948161748012d8a2",
        "source_schema_version": "004_v1_part5_backup_restore.sql",
        "source_tenant_identifier": "sgp_v1_tenant_source",
        "created_at_utc": now,
        "record_counts": {**{section: len(rows) for section, rows in data.items()}, "attachments": 1},
        "attachment_count": 1,
        "total_attachment_bytes": len(pdf),
        "data_file_inventory": data_inventory,
        "attachment_inventory": attachment_inventory,
        "minimum_compatible_restore_version": "0.1.0-v1-part5",
        "contains_secrets": False,
        "overall_backup_integrity": f"sha256:{_sha(_json_bytes({'data': data, 'attachments': attachment_inventory}))}",
    }
    return _encrypt_payload({"manifest": manifest, "data": data, "attachments": [attachment]})


def _override(user: dict):
    async def _get():
        return {**user}

    return _get


async def _client_as(user: dict) -> AsyncClient:
    app.dependency_overrides[get_current_user] = _override(user)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _clear() -> None:
    app.dependency_overrides.pop(get_current_user, None)


def _files(content: bytes):
    return {"file": ("synthetic.signguy-backup", content, "application/vnd.signguy.backup")}


@pytest.mark.asyncio
async def test_preview_validates_backup_without_mutating_and_rejects_wrong_passphrase(seeded_users, clean_db):
    user = seeded_users["user_a"]
    content = _backup_bytes(user["email"])
    async with await _client_as(user) as client:
        wrong = await client.post(
            "/api/slim-import/preview",
            data={"passphrase": "wrong passphrase value", "target_tenant_id": user["tenant_id"]},
            files=_files(content),
        )
        assert wrong.status_code == 400
        assert wrong.json()["detail"] == "backup_decryption_failed"

        preview = await client.post(
            "/api/slim-import/preview",
            data={"passphrase": PASSPHRASE, "target_tenant_id": user["tenant_id"]},
            files=_files(content),
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["import_permitted"] is True
        assert body["record_counts"]["customers"] == 1
        assert body["number_mappings"]["orders"][0]["preserve_number"] == 9
        assert await clean_db.customers.count_documents({"tenant_id": user["tenant_id"]}) == 0
    _clear()


@pytest.mark.asyncio
async def test_non_empty_target_cross_tenant_and_staff_are_blocked(seeded_users, clean_db):
    user = seeded_users["user_a"]
    staff = {key: value for key, value in user.items() if key != "_id"}
    staff.update({"id": f"staff-{uuid.uuid4().hex[:8]}", "role": "staff", "email": f"staff-{uuid.uuid4().hex[:8]}@example.com"})
    await clean_db.users.insert_one(staff)
    content = _backup_bytes(user["email"])
    await clean_db.customers.insert_one({"id": f"existing-{uuid.uuid4().hex[:8]}", "tenant_id": user["tenant_id"], "name": "Existing"})

    async with await _client_as(user) as client:
        preview = await client.post(
            "/api/slim-import/preview",
            data={"passphrase": PASSPHRASE, "target_tenant_id": user["tenant_id"]},
            files=_files(content),
        )
        assert preview.status_code == 200
        assert preview.json()["import_permitted"] is False
        assert any(item.startswith("Customers:1") for item in preview.json()["blocking_errors"])

        cross = await client.post(
            "/api/slim-import/preview",
            data={"passphrase": PASSPHRASE, "target_tenant_id": seeded_users["tenant_b"]["id"]},
            files=_files(content),
        )
        assert cross.status_code == 403
        assert cross.json()["detail"] == "cross_tenant_import_denied"

    async with await _client_as(staff) as client:
        denied = await client.post(
            "/api/slim-import/preview",
            data={"passphrase": PASSPHRASE, "target_tenant_id": staff["tenant_id"]},
            files=_files(content),
        )
        assert denied.status_code == 403
        assert denied.json()["detail"] == "permission_denied"
    _clear()


@pytest.mark.asyncio
async def test_confirm_import_preserves_relationships_attachment_sequences_and_blocks_duplicate(seeded_users, clean_db):
    user = seeded_users["user_a"]
    target = seeded_users["tenant_a"]
    content = _backup_bytes(user["email"])
    async with await _client_as(user) as client:
        result = await client.post(
            "/api/slim-import/confirm",
            data={
                "passphrase": PASSPHRASE,
                "target_tenant_id": user["tenant_id"],
                "confirmation_phrase": target["name"],
                "import_unassigned": "false",
            },
            files=_files(content),
        )
        assert result.status_code == 200, result.text
        report = result.json()
        assert report["status"] == "completed"
        assert report["counts_imported"]["customers"] == 1
        assert report["attachment_results"]["imported"] == 1

        customer = await clean_db.customers.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        quote = await clean_db.quotes.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        order = await clean_db.orders.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        item = await clean_db.order_items.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        work_order = await clean_db.work_orders.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        invoice = await clean_db.invoices.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        calendar = await clean_db.calendar_events.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        file_doc = await clean_db.files.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})
        attachment = await clean_db.attachments.find_one({"tenant_id": user["tenant_id"]}, {"_id": 0})

        assert customer["number"] == 7
        assert quote["number"] == 8
        assert order["number"] == 9
        assert quote["converted_order_id"] == order["id"]
        assert item["order_id"] == order["id"]
        assert item["unit_price_cents"] == 5000
        assert item["production_required"] is True
        assert work_order["order_id"] == order["id"]
        assert work_order["production_status"] == "in_progress"
        assert invoice["order_id"] == order["id"]
        assert invoice["amount_paid_cents"] == 5000
        assert await clean_db.payments.count_documents({"tenant_id": user["tenant_id"]}) == 0
        assert calendar["status"] == "completed"
        assert calendar["order_item_id"] == item["id"]
        assert file_doc["visibility"] == "internal"
        assert attachment["file_id"] == file_doc["id"]
        assert attachment["parent_id"] == order["id"]

        duplicate = await client.post(
            "/api/slim-import/confirm",
            data={
                "passphrase": PASSPHRASE,
                "target_tenant_id": user["tenant_id"],
                "confirmation_phrase": target["name"],
                "import_unassigned": "false",
            },
            files=_files(content),
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "slim_import_blocked"
        assert await clean_db.orders.count_documents({"tenant_id": user["tenant_id"]}) == 1
    _clear()


@pytest.mark.asyncio
async def test_tampered_manifest_checksum_is_rejected(seeded_users):
    user = seeded_users["user_a"]
    backup = bytearray(_backup_bytes(user["email"]))
    backup[-12] = backup[-12] ^ 1
    async with await _client_as(user) as client:
        response = await client.post(
            "/api/slim-import/preview",
            data={"passphrase": PASSPHRASE, "target_tenant_id": user["tenant_id"]},
            files=_files(bytes(backup)),
        )
        assert response.status_code == 400
        assert response.json()["detail"] in {"backup_decryption_failed", "backup_container_unrecognized"}
    _clear()

from __future__ import annotations

import base64
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Iterable, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.file import Attachment, FileRecord
from ..models.work_order import WorkOrder
from ..services import storage
from ..services.audit import record_audit
from ..services.sequence import advance_record_number_counter_at_least, next_record_number


BACKUP_SIGNATURE = "SIGNGUY-SLIM-BACKUP"
CONTAINER_VERSION = "1.0.0"
FORMAT_VERSION = "signguy-slim-backup-v1"
PORTABLE_CONTRACT_VERSION = "1.0.0"
SOURCE_PRODUCT = "SIGNGUY-SLIM"
KDF = "PBKDF2-HMAC-SHA256"
KDF_ITERATIONS = 310_000
KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 12
TAG_BYTES = 16
MAX_BACKUP_BYTES = 25 * 1024 * 1024
SUPPORTED_SOURCE_SCHEMA_VERSIONS = {"004_v1_part5_backup_restore.sql"}
SUPPORTED_ATTACHMENT_TYPES = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
    "text/plain": {".txt", ".text", ".log"},
    "text/csv": {".csv"},
    "application/json": {".json"},
}
BLOCKED_EXTENSION_RE = re.compile(
    r"\.(app|apk|bat|cmd|com|cpl|dll|dmg|exe|gadget|hta|html?|iso|jar|js|jse|jsx|lnk|mjs|msi|php|pl|ps1|py|rb|reg|scr|sh|svg|swf|ts|tsx|vb|vbe|vbs|wsf|xml)$",
    re.IGNORECASE,
)
EXPECTED_DATA_SECTIONS = [
    "tenants",
    "users",
    "customers",
    "estimates",
    "estimate_items",
    "orders",
    "order_items",
    "invoices",
    "calendar_events",
    "tenant_sequences",
    "reminders",
    "notes",
    "audit_events",
]
EXPECTED_RECORD_COUNT_KEYS = [*EXPECTED_DATA_SECTIONS, "attachments"]
EMPTY_CHECKS: dict[str, str] = {
    "Customers": "customers",
    "Quotes": "quotes",
    "Quote Line Items": "quote_line_items",
    "Orders": "orders",
    "Order Items": "order_items",
    "Work Orders": "work_orders",
    "Invoices": "invoices",
    "Invoice Line Items": "invoice_line_items",
    "Payments": "payments",
    "Calendar Events": "calendar_events",
    "Files": "files",
    "Attachments": "attachments",
    "Slim Import Mappings": "slim_import_mappings",
}
SOURCE_TO_TARGET_TYPES = {
    "customers": "customer",
    "estimates": "quote",
    "estimate_items": "quote_line_item",
    "orders": "order",
    "order_items": "order_item",
    "invoices": "invoice",
    "calendar_events": "calendar_event",
    "attachments": "file",
}
SLIM_STAGE_TO_MVP_STATUS = {
    "not_started": "released",
    "queued": "queued",
    "in_progress": "in_progress",
    "blocked": "blocked",
    "ready": "ready",
    "completed": "completed",
}


class SlimImportError(ValueError):
    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class ValidatedBackup:
    manifest: dict[str, Any]
    data: dict[str, list[dict[str, Any]]]
    attachments: list[dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _uuid() -> str:
    return str(uuid.uuid4())


def _clean_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _clean_cents(value: Any) -> int:
    return max(0, _clean_int(value, 0))


def _parse_source_number(value: Any, prefix: str) -> Optional[int]:
    match = re.match(rf"^{re.escape(prefix)}-(\d+)$", str(value or ""))
    return int(match.group(1)) if match else None


def _source_number_preview(value: Any, prefix: str) -> dict[str, Any]:
    parsed = _parse_source_number(value, prefix)
    return {
        "source_number": value,
        "preserve_number": parsed,
        "renumber_required": parsed is None,
    }


def _safe_filename(filename: str) -> str:
    raw = str(filename or "attachment").replace("\\", "/")
    safe = raw.rsplit("/", 1)[-1]
    if not safe or safe != raw or BLOCKED_EXTENSION_RE.search(safe):
        raise SlimImportError("backup_attachment_type_unsupported")
    return safe


def _assert_safe_package_path(path: Any) -> None:
    if not isinstance(path, str) or not path or "\\" in path:
        raise SlimImportError("backup_path_invalid")
    parts = PurePosixPath(path).parts
    if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise SlimImportError("backup_path_invalid")


def _assert_attachment_bytes(data: bytes, mime_type: str, filename: str) -> None:
    safe = _safe_filename(filename)
    ext = "." + safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    if mime_type not in SUPPORTED_ATTACHMENT_TYPES or ext not in SUPPORTED_ATTACHMENT_TYPES[mime_type]:
        raise SlimImportError("backup_attachment_type_unsupported")
    if mime_type == "application/pdf" and not data.startswith(b"%PDF-"):
        raise SlimImportError("backup_attachment_type_unsupported")
    if mime_type == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SlimImportError("backup_attachment_type_unsupported")
    if mime_type == "image/jpeg" and not data.startswith(b"\xff\xd8\xff"):
        raise SlimImportError("backup_attachment_type_unsupported")
    if mime_type == "image/gif" and data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise SlimImportError("backup_attachment_type_unsupported")
    if mime_type == "image/webp" and not (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        raise SlimImportError("backup_attachment_type_unsupported")
    if mime_type in {"text/plain", "text/csv", "application/json"}:
        if b"\x00" in data:
            raise SlimImportError("backup_attachment_type_unsupported")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SlimImportError("backup_attachment_type_unsupported") from exc
        if re.match(r"^(<!doctype\s+html|<html\b|<script\b|<svg\b|<\?xml)", text.lstrip(), re.IGNORECASE):
            raise SlimImportError("backup_attachment_type_unsupported")
        if mime_type == "application/json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise SlimImportError("backup_attachment_type_unsupported") from exc


def _decode_b64(value: Any, code: str) -> bytes:
    try:
        return base64.b64decode(str(value or ""), validate=True)
    except Exception as exc:
        raise SlimImportError(code) from exc


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, KDF_ITERATIONS, KEY_BYTES)


def decrypt_backup(content: bytes, passphrase: str) -> dict[str, Any]:
    if not isinstance(passphrase, str) or len(passphrase) < 12 or len(passphrase) > 256:
        raise SlimImportError("backup_passphrase_invalid")
    if not content or len(content) > MAX_BACKUP_BYTES:
        raise SlimImportError("backup_file_too_large", 413)
    try:
        container = json.loads(content.decode("utf-8"))
    except Exception as exc:
        raise SlimImportError("backup_container_unrecognized") from exc
    expected_keys = {
        "signature",
        "container_version",
        "algorithm",
        "kdf",
        "kdf_iterations",
        "salt_b64",
        "nonce_b64",
        "tag_b64",
        "ciphertext_b64",
    }
    if set(container.keys()) != expected_keys:
        raise SlimImportError("backup_container_unrecognized")
    if container["signature"] != BACKUP_SIGNATURE or container["container_version"] != CONTAINER_VERSION:
        raise SlimImportError("backup_container_unrecognized")
    if container["algorithm"] != "AES-256-GCM" or container["kdf"] != KDF or container["kdf_iterations"] != KDF_ITERATIONS:
        raise SlimImportError("backup_format_unsupported")
    salt = _decode_b64(container["salt_b64"], "backup_container_unrecognized")
    nonce = _decode_b64(container["nonce_b64"], "backup_container_unrecognized")
    tag = _decode_b64(container["tag_b64"], "backup_container_unrecognized")
    ciphertext = _decode_b64(container["ciphertext_b64"], "backup_container_unrecognized")
    if len(salt) != SALT_BYTES or len(nonce) != NONCE_BYTES or len(tag) != TAG_BYTES or not ciphertext or len(ciphertext) > MAX_BACKUP_BYTES:
        raise SlimImportError("backup_container_unrecognized")
    aad = {
        "signature": container["signature"],
        "container_version": container["container_version"],
        "algorithm": container["algorithm"],
        "kdf": container["kdf"],
        "kdf_iterations": container["kdf_iterations"],
    }
    try:
        plaintext = AESGCM(_derive_key(passphrase, salt)).decrypt(nonce, ciphertext + tag, _json_bytes(aad))
        return json.loads(plaintext.decode("utf-8"))
    except (InvalidTag, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SlimImportError("backup_decryption_failed") from exc


def _assert_unique(values: Iterable[Any], code: str) -> None:
    seen: set[Any] = set()
    for value in values:
        if value in seen:
            raise SlimImportError(code)
        seen.add(value)


def validate_payload(payload: dict[str, Any]) -> ValidatedBackup:
    manifest = payload.get("manifest") if isinstance(payload, dict) else None
    if not manifest:
        raise SlimImportError("backup_manifest_missing")
    if manifest.get("source_product") != SOURCE_PRODUCT or manifest.get("backup_format_version") != FORMAT_VERSION:
        raise SlimImportError("backup_format_unsupported")
    if manifest.get("portable_contract_version") != PORTABLE_CONTRACT_VERSION:
        raise SlimImportError("backup_format_unsupported")
    if manifest.get("contains_secrets") is not False:
        raise SlimImportError("backup_contains_secrets")
    if manifest.get("source_schema_version") not in SUPPORTED_SOURCE_SCHEMA_VERSIONS:
        raise SlimImportError("backup_schema_unsupported")
    if set(payload.keys()) != {"manifest", "data", "attachments"}:
        raise SlimImportError("backup_manifest_malformed")
    data = payload["data"]
    attachments = payload["attachments"]
    if set(data.keys()) != set(EXPECTED_DATA_SECTIONS) or not isinstance(attachments, list):
        raise SlimImportError("backup_manifest_malformed")
    for section in EXPECTED_DATA_SECTIONS:
        if not isinstance(data.get(section), list):
            raise SlimImportError("backup_manifest_malformed")
    if len(data["tenants"]) != 1:
        raise SlimImportError("backup_manifest_malformed")

    counts = {section: len(data[section]) for section in EXPECTED_DATA_SECTIONS}
    counts["attachments"] = len(attachments)
    if set((manifest.get("record_counts") or {}).keys()) != set(EXPECTED_RECORD_COUNT_KEYS):
        raise SlimImportError("backup_manifest_malformed")
    for section, count in counts.items():
        if manifest["record_counts"].get(section) != count:
            raise SlimImportError("backup_record_count_mismatch")

    expected_files = {
        f"data/{section}.json": {
            "path": f"data/{section}.json",
            "media_type": "application/json",
            "size_bytes": len(_json_bytes(data[section])),
            "sha256": _sha256(_json_bytes(data[section])),
        }
        for section in EXPECTED_DATA_SECTIONS
    }
    inventory = manifest.get("data_file_inventory")
    if not isinstance(inventory, list) or len(inventory) != len(expected_files):
        raise SlimImportError("backup_manifest_malformed")
    _assert_unique((entry.get("path") for entry in inventory), "backup_manifest_malformed")
    for entry in inventory:
        _assert_safe_package_path(entry.get("path"))
        expected = expected_files.get(entry.get("path"))
        if not expected or any(entry.get(key) != expected[key] for key in ("media_type", "size_bytes", "sha256")):
            raise SlimImportError("backup_checksum_mismatch")

    attachment_inventory = manifest.get("attachment_inventory")
    if not isinstance(attachment_inventory, list):
        raise SlimImportError("backup_manifest_malformed")
    _assert_unique((entry.get("path") for entry in attachment_inventory), "backup_manifest_malformed")
    _assert_unique((entry.get("source_portable_id") for entry in attachment_inventory), "backup_manifest_malformed")
    attachment_by_portable = {}
    for entry in attachment_inventory:
        _assert_safe_package_path(entry.get("path"))
        attachment_by_portable[entry.get("source_portable_id")] = entry
    if len(attachment_by_portable) != len(attachments):
        raise SlimImportError("backup_attachment_missing")

    source_tenant_id = data["tenants"][0].get("id")
    for section in ["users", "customers", "estimates", "estimate_items", "orders", "order_items", "invoices", "calendar_events", "tenant_sequences", "audit_events"]:
        for row in data[section]:
            if row.get("tenant_id") != source_tenant_id:
                raise SlimImportError("backup_relationship_invalid")
    if any("password_hash" in row for row in data["users"]):
        raise SlimImportError("backup_contains_secrets")

    users = {row.get("id") for row in data["users"]}
    customers = {row.get("id") for row in data["customers"]}
    estimates = {row.get("id") for row in data["estimates"]}
    estimate_items = {row.get("id") for row in data["estimate_items"]}
    orders = {row.get("id") for row in data["orders"]}
    order_items = {row.get("id") for row in data["order_items"]}
    for section in ["users", "customers", "estimates", "estimate_items", "orders", "order_items", "invoices", "calendar_events"]:
        _assert_unique((row.get("id") for row in data[section]), "backup_relationship_invalid")
    for row in data["estimates"]:
        if row.get("customer_id") not in customers or (row.get("converted_order_id") and row["converted_order_id"] not in orders):
            raise SlimImportError("backup_relationship_invalid")
    for row in data["estimate_items"]:
        if row.get("estimate_id") not in estimates or (row.get("assigned_user_id") and row["assigned_user_id"] not in users):
            raise SlimImportError("backup_relationship_invalid")
    for row in data["orders"]:
        if row.get("customer_id") not in customers or (row.get("source_estimate_id") and row["source_estimate_id"] not in estimates):
            raise SlimImportError("backup_relationship_invalid")
    for row in data["order_items"]:
        if row.get("order_id") not in orders or (row.get("source_estimate_item_id") and row["source_estimate_item_id"] not in estimate_items) or (row.get("assigned_user_id") and row["assigned_user_id"] not in users):
            raise SlimImportError("backup_relationship_invalid")
    for row in data["invoices"]:
        if row.get("order_id") not in orders or row.get("customer_id") not in customers:
            raise SlimImportError("backup_relationship_invalid")
    for row in data["calendar_events"]:
        if (row.get("order_id") and row["order_id"] not in orders) or (row.get("order_item_id") and row["order_item_id"] not in order_items) or (row.get("assigned_user_id") and row["assigned_user_id"] not in users) or (row.get("created_by_user_id") and row["created_by_user_id"] not in users):
            raise SlimImportError("backup_relationship_invalid")

    total_attachment_bytes = 0
    for attachment in attachments:
        metadata = attachment.get("metadata") or {}
        entry = attachment_by_portable.get(metadata.get("portable_id"))
        if not entry:
            raise SlimImportError("backup_attachment_missing")
        if metadata.get("order_id") not in orders or metadata.get("tenant_id") != source_tenant_id:
            raise SlimImportError("backup_relationship_invalid")
        content = _decode_b64(attachment.get("content_base64"), "backup_checksum_mismatch")
        if entry.get("content_type") != metadata.get("mime_type") or entry.get("size_bytes") != metadata.get("byte_size") or entry.get("sha256") != metadata.get("sha256"):
            raise SlimImportError("backup_checksum_mismatch")
        if len(content) != entry.get("size_bytes") or _sha256(content) != entry.get("sha256"):
            raise SlimImportError("backup_checksum_mismatch")
        _assert_attachment_bytes(content, metadata.get("mime_type"), metadata.get("original_filename"))
        total_attachment_bytes += len(content)

    if manifest.get("attachment_count") != len(attachments) or manifest.get("total_attachment_bytes") != total_attachment_bytes:
        raise SlimImportError("backup_record_count_mismatch")
    integrity_input = _json_bytes({"data": data, "attachments": attachment_inventory})
    if manifest.get("overall_backup_integrity") != f"sha256:{_sha256(integrity_input)}":
        raise SlimImportError("backup_checksum_mismatch")
    return ValidatedBackup(manifest=manifest, data=data, attachments=attachments)


def decrypt_and_validate(content: bytes, passphrase: str) -> ValidatedBackup:
    return validate_payload(decrypt_backup(content, passphrase))


def _source_users_by_id(backup: ValidatedBackup) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in backup.data["users"]}


def _source_user_portable(source_users: dict[str, dict[str, Any]], user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    return source_users.get(user_id, {}).get("portable_id")


async def _assignment_mapping(tenant_id: str, backup: ValidatedBackup) -> list[dict[str, Any]]:
    mapping = []
    for source in backup.data["users"]:
        email = str(source.get("email_label") or source.get("email") or "").lower()
        matches = await db.users.find({"tenant_id": tenant_id, "email": email, "is_active": True}, {"_id": 0}).to_list(length=3)
        mapping.append({
            "source_user_id": source.get("id"),
            "source_user_portable_id": source.get("portable_id"),
            "source_display_name": source.get("display_name") or source.get("full_name"),
            "source_email_label": source.get("email_label") or source.get("email"),
            "matched_target_user_id": matches[0]["id"] if len(matches) == 1 else None,
            "matched_target_email": matches[0]["email"] if len(matches) == 1 else None,
            "matched": len(matches) == 1,
            "ambiguous": len(matches) > 1,
        })
    return mapping


async def _target_empty_counts(tenant_id: str) -> dict[str, int]:
    counts = {}
    for label, collection in EMPTY_CHECKS.items():
        counts[label] = await db[collection].count_documents({"tenant_id": tenant_id})
    successful = await db.slim_import_runs.count_documents({"tenant_id": tenant_id, "status": "completed"})
    counts["Prior Successful Slim Import Receipt"] = successful
    return counts


async def preview_import(*, target_tenant_id: str, actor: dict[str, Any], content: bytes, passphrase: str) -> dict[str, Any]:
    _require_owner_admin(actor)
    _assert_actor_can_target(actor, target_tenant_id)
    backup = decrypt_and_validate(content, passphrase)
    counts = await _target_empty_counts(target_tenant_id)
    blocking_errors = [f"{label}:{count}" for label, count in counts.items() if count > 0]
    duplicate = await db.slim_import_runs.find_one({
        "tenant_id": target_tenant_id,
        "backup_id": backup.manifest["backup_id"],
        "status": "completed",
    })
    if duplicate:
        blocking_errors.append("duplicate_backup")
    user_mapping = await _assignment_mapping(target_tenant_id, backup)
    if any(entry["ambiguous"] for entry in user_mapping):
        blocking_errors.append("ambiguous_user_mapping")
    unresolved = [entry for entry in user_mapping if not entry["matched"] and not entry["ambiguous"]]
    warnings = [
        f"Source user {entry['source_email_label']} is unresolved; affected assignments require explicit import_unassigned."
        for entry in unresolved
    ]
    return {
        "backup_id": backup.manifest["backup_id"],
        "source_product": backup.manifest["source_product"],
        "backup_format_version": backup.manifest["backup_format_version"],
        "portable_contract_version": backup.manifest["portable_contract_version"],
        "source_application_version": backup.manifest.get("source_application_version"),
        "source_schema_version": backup.manifest.get("source_schema_version"),
        "source_tenant_identifier": backup.manifest.get("source_tenant_identifier"),
        "created_at_utc": backup.manifest.get("created_at_utc"),
        "target_tenant_id": target_tenant_id,
        "target_empty_counts": counts,
        "record_counts": backup.manifest["record_counts"],
        "attachment_count": backup.manifest["attachment_count"],
        "total_attachment_bytes": backup.manifest["total_attachment_bytes"],
        "number_mappings": _number_preview(backup),
        "production_stage_mappings": _production_stage_preview(backup),
        "user_mapping": user_mapping,
        "settings": _settings_preview(backup),
        "skipped_fields": _skipped_fields(),
        "warnings": warnings,
        "blocking_errors": blocking_errors,
        "import_permitted": not blocking_errors,
        "requires_unassigned_acknowledgement": bool(unresolved),
    }


def _number_preview(backup: ValidatedBackup) -> dict[str, list[dict[str, Any]]]:
    return {
        "customers": [_source_number_preview(row.get("customer_number"), "C") | {"source_id": row.get("id")} for row in backup.data["customers"]],
        "quotes": [_source_number_preview(row.get("estimate_number"), "E") | {"source_id": row.get("id")} for row in backup.data["estimates"]],
        "orders": [_source_number_preview(row.get("order_number"), "O") | {"source_id": row.get("id")} for row in backup.data["orders"]],
        "invoices": [_source_number_preview(row.get("invoice_number"), "I") | {"source_id": row.get("id")} for row in backup.data["invoices"]],
    }


def _production_stage_preview(backup: ValidatedBackup) -> list[dict[str, Any]]:
    rows = []
    for item in backup.data["order_items"]:
        if not item.get("production_required"):
            continue
        source_stage = item.get("production_stage") or "not_started"
        rows.append({
            "source_order_item_id": item.get("id"),
            "source_stage": source_stage,
            "target_work_order_status": SLIM_STAGE_TO_MVP_STATUS.get(source_stage),
            "blocking": source_stage not in SLIM_STAGE_TO_MVP_STATUS,
        })
    return rows


def _settings_preview(backup: ValidatedBackup) -> dict[str, Any]:
    tenant = backup.data["tenants"][0]
    return {
        "imported": {
            key: tenant.get(key)
            for key in [
                "company_name",
                "logo_reference",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "postal_code",
                "country",
                "contact_email",
                "contact_phone",
                "sales_tax_rate_basis_points",
                "locale",
                "currency",
                "shop_timezone",
            ]
            if tenant.get(key) is not None
        },
        "skipped": ["platform settings", "subscription state", "API keys", "integrations", "pricing-engine defaults", "security policy"],
    }


def _skipped_fields() -> dict[str, list[str]]:
    return {
        "payments": ["Stripe charges", "processor transactions", "processor payment references"],
        "production": ["timers", "machine time", "station checkout", "capacity", "materials", "resource scheduling"],
        "users": ["passwords", "password hashes", "sessions", "tokens"],
        "modules": ["Webstores", "Customer Portal", "Decision Room", "AI", "inventory", "payroll/time-clock"],
    }


def _require_owner_admin(actor: dict[str, Any]) -> None:
    if actor.get("role") not in {"owner", "admin"}:
        raise SlimImportError("permission_denied", 403)


def _assert_actor_can_target(actor: dict[str, Any], target_tenant_id: str) -> None:
    if actor.get("tenant_id") != target_tenant_id:
        raise SlimImportError("cross_tenant_import_denied", 403)


async def _number_for_source(
    *,
    tenant_id: str,
    record_type: str,
    source_number: Any,
    prefix: str,
    import_run_id: str,
    source_id: str,
    actor: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    parsed = _parse_source_number(source_number, prefix)
    if parsed is not None:
        return parsed, {"source_number": source_number, "target_number": parsed, "preserved": True}
    allocation = await next_record_number(
        tenant_id=tenant_id,
        record_type=record_type,
        idempotency_key=f"slim-import:{import_run_id}:{record_type}:{source_id}",
        issued_to_entity_type=record_type,
        actor_user_id=actor["id"],
        actor_email=actor["email"],
        reason="slim_backup_import",
    )
    return allocation.number, {"source_number": source_number, "target_number": allocation.number, "preserved": False}


async def _advance_sequences(tenant_id: str, maxima: dict[str, int]) -> None:
    for record_type, value in maxima.items():
        if value > 0:
            await advance_record_number_counter_at_least(tenant_id=tenant_id, record_type=record_type, value=value)


def _map_status(value: Any, allowed: set[str], default: str) -> str:
    status = str(value or "").lower()
    return status if status in allowed else default


async def confirm_import(
    *,
    target_tenant_id: str,
    actor: dict[str, Any],
    content: bytes,
    passphrase: str,
    confirmation_phrase: str,
    import_unassigned: bool,
) -> dict[str, Any]:
    _require_owner_admin(actor)
    _assert_actor_can_target(actor, target_tenant_id)
    target = await db.tenants.find_one({"id": target_tenant_id}, {"_id": 0})
    if not target:
        raise SlimImportError("target_tenant_not_found", 404)
    if confirmation_phrase != target.get("name"):
        raise SlimImportError("backup_confirmation_required")
    backup = decrypt_and_validate(content, passphrase)
    preview = await preview_import(target_tenant_id=target_tenant_id, actor=actor, content=content, passphrase=passphrase)
    if preview["requires_unassigned_acknowledgement"] and not import_unassigned:
        raise SlimImportError("backup_assignment_policy_required")
    if preview["blocking_errors"]:
        raise SlimImportError("slim_import_blocked", 409)

    import_run_id = _uuid()
    started_at = _now_iso()
    run_doc = {
        "id": import_run_id,
        "tenant_id": target_tenant_id,
        "backup_id": backup.manifest["backup_id"],
        "source_product": backup.manifest["source_product"],
        "source_format_version": backup.manifest["backup_format_version"],
        "source_schema_version": backup.manifest["source_schema_version"],
        "source_tenant_identifier": backup.manifest["source_tenant_identifier"],
        "actor_user_id": actor["id"],
        "status": "pending",
        "started_at": started_at,
        "completed_at": None,
        "record_counts": backup.manifest["record_counts"],
        "warnings": preview["warnings"],
        "errors": [],
        "report": {},
    }
    await db.slim_import_runs.insert_one(prepare_for_mongo(run_doc))
    await record_audit(
        tenant_id=target_tenant_id,
        actor_user_id=actor["id"],
        actor_email=actor["email"],
        action="slim_import.confirmed",
        entity_type="slim_import_run",
        entity_id=import_run_id,
        summary="SignGuy Slim import confirmed",
        diff={"backup_id": backup.manifest["backup_id"]},
    )

    staged_storage_keys: list[str] = []
    inserted: dict[str, list[str]] = {}
    try:
        latest_counts = await _target_empty_counts(target_tenant_id)
        if any(count > 0 for count in latest_counts.values()):
            raise SlimImportError("slim_import_blocked", 409)
        await db.slim_import_runs.update_one({"id": import_run_id}, {"$set": {"status": "running", "updated_at": _now_iso()}})
        translated = await _translate_records(target_tenant_id, actor, backup, preview, import_run_id)
        for file_doc in translated["files"]:
            storage.put_bytes(file_doc["storage_key"], file_doc.pop("_content"), file_doc["mime_type"])
            staged_storage_keys.append(file_doc["storage_key"])
        for collection, rows in translated["collections"].items():
            if rows:
                await db[collection].insert_many([prepare_for_mongo(row) for row in rows])
                inserted[collection] = [row["id"] for row in rows]
        await _advance_sequences(target_tenant_id, translated["sequence_maxima"])
        completed_at = _now_iso()
        report = {
            "import_id": import_run_id,
            "backup_id": backup.manifest["backup_id"],
            "source_product": SOURCE_PRODUCT,
            "target_product": "SIGNGUY-MVP",
            "source_schema_version": backup.manifest["source_schema_version"],
            "target_tenant_id": target_tenant_id,
            "start_time": started_at,
            "end_time": completed_at,
            "importing_user": {"id": actor["id"], "email": actor["email"]},
            "status": "completed",
            "counts_requested": backup.manifest["record_counts"],
            "counts_imported": translated["counts"],
            "attachment_results": {"imported": len(translated["files"]), "private_storage": True},
            "number_mappings": translated["number_mappings"],
            "user_mappings": preview["user_mapping"],
            "unassigned_records": translated["unassigned_records"],
            "warnings": preview["warnings"],
            "errors": [],
            "rollback_cleanup": "not_required",
            "sequence_result": translated["sequence_maxima"],
        }
        await db.slim_import_runs.update_one(
            {"id": import_run_id, "tenant_id": target_tenant_id},
            {"$set": {"status": "completed", "completed_at": completed_at, "report": report, "updated_at": completed_at}},
        )
        await record_audit(
            tenant_id=target_tenant_id,
            actor_user_id=actor["id"],
            actor_email=actor["email"],
            action="slim_import.succeeded",
            entity_type="slim_import_run",
            entity_id=import_run_id,
            summary="SignGuy Slim import completed",
            diff={"backup_id": backup.manifest["backup_id"], "counts": translated["counts"]},
        )
        return report
    except Exception as exc:
        for collection, ids in inserted.items():
            await db[collection].delete_many({"tenant_id": target_tenant_id, "id": {"$in": ids}})
        for storage_key in staged_storage_keys:
            storage.delete_bytes(storage_key)
        code = exc.code if isinstance(exc, SlimImportError) else "slim_import_failed"
        await db.slim_import_runs.update_one(
            {"id": import_run_id, "tenant_id": target_tenant_id},
            {"$set": {"status": "failed", "completed_at": _now_iso(), "errors": [code], "report.rollback_cleanup": "completed"}},
        )
        await record_audit(
            tenant_id=target_tenant_id,
            actor_user_id=actor["id"],
            actor_email=actor["email"],
            action="slim_import.failed",
            entity_type="slim_import_run",
            entity_id=import_run_id,
            summary="SignGuy Slim import failed and was rolled back",
            diff={"backup_id": backup.manifest["backup_id"], "error": code},
        )
        if isinstance(exc, SlimImportError):
            raise
        raise SlimImportError("slim_import_failed", 500) from exc


async def _translate_records(
    tenant_id: str,
    actor: dict[str, Any],
    backup: ValidatedBackup,
    preview: dict[str, Any],
    import_run_id: str,
) -> dict[str, Any]:
    source = backup.data
    ids: dict[str, dict[str, str]] = {
        name: {row["id"]: _uuid() for row in source[name]}
        for name in ["customers", "estimates", "estimate_items", "orders", "order_items", "invoices", "calendar_events"]
    }
    ids["attachments"] = {entry["metadata"]["id"]: _uuid() for entry in backup.attachments}
    user_by_id = _source_users_by_id(backup)
    target_by_source_user_portable = {
        entry["source_user_portable_id"]: entry["matched_target_user_id"]
        for entry in preview["user_mapping"]
        if entry.get("matched_target_user_id")
    }
    unassigned_records: list[dict[str, Any]] = []

    def map_user(source_user_id: Optional[str], source_type: str, source_id: str) -> Optional[str]:
        portable_id = _source_user_portable(user_by_id, source_user_id)
        target = target_by_source_user_portable.get(portable_id)
        if source_user_id and not target:
            unassigned_records.append({"source_type": source_type, "source_id": source_id, "source_user_id": source_user_id})
        return target

    collections: dict[str, list[dict[str, Any]]] = {
        "customers": [],
        "quotes": [],
        "quote_line_items": [],
        "orders": [],
        "order_items": [],
        "work_orders": [],
        "invoices": [],
        "invoice_line_items": [],
        "calendar_events": [],
        "files": [],
        "attachments": [],
        "slim_import_mappings": [],
    }
    number_mappings = {"customers": [], "quotes": [], "orders": [], "invoices": [], "work_orders": []}
    sequence_maxima = {"customer": 0, "quote": 0, "order": 0, "invoice": 0, "work_order": 0}

    for row in source["customers"]:
        number, mapping = await _number_for_source(tenant_id=tenant_id, record_type="customer", source_number=row.get("customer_number"), prefix="C", import_run_id=import_run_id, source_id=row["id"], actor=actor)
        sequence_maxima["customer"] = max(sequence_maxima["customer"], number)
        number_mappings["customers"].append(mapping | {"source_id": row["id"], "target_id": ids["customers"][row["id"]]})
        collections["customers"].append({
            "id": ids["customers"][row["id"]],
            "tenant_id": tenant_id,
            "number": number,
            "name": row.get("contact_name") or row.get("business_name") or "Imported Customer",
            "company": row.get("business_name"),
            "customer_type": "business" if row.get("business_name") else "individual",
            "lifecycle_status": "active" if row.get("active", True) else "inactive",
            "email": row.get("email") or None,
            "phone": row.get("phone") or None,
            "address_line1": row.get("billing_line1"),
            "address_line2": row.get("billing_line2"),
            "city": row.get("billing_city"),
            "state": row.get("billing_state"),
            "postal_code": row.get("billing_postal_code"),
            "country": row.get("billing_country"),
            "notes": row.get("internal_notes"),
            "archived": False,
            "import_provenance": _provenance(backup, import_run_id, "customers", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })

    for row in source["estimates"]:
        number, mapping = await _number_for_source(tenant_id=tenant_id, record_type="quote", source_number=row.get("estimate_number"), prefix="E", import_run_id=import_run_id, source_id=row["id"], actor=actor)
        sequence_maxima["quote"] = max(sequence_maxima["quote"], number)
        number_mappings["quotes"].append(mapping | {"source_id": row["id"], "target_id": ids["estimates"][row["id"]]})
        collections["quotes"].append({
            "id": ids["estimates"][row["id"]],
            "tenant_id": tenant_id,
            "number": number,
            "customer_id": ids["customers"][row["customer_id"]],
            "job_name": f"Imported Slim Estimate {row.get('estimate_number') or number}",
            "notes": row.get("internal_notes"),
            "notes_internal": row.get("internal_notes"),
            "revision_number": 1,
            "expires_at": row.get("expires_at"),
            "subtotal_cents": _clean_cents(row.get("subtotal_cents")),
            "discount_cents": _clean_cents(row.get("discount_cents")),
            "tax_cents": _clean_cents(row.get("tax_cents")),
            "total_cents": _clean_cents(row.get("total_cents")),
            "status": _map_status(row.get("status"), {"draft", "sent", "viewed", "approved", "declined", "expired", "converted", "void"}, "draft"),
            "converted_order_id": ids["orders"].get(row.get("converted_order_id")),
            "created_by": actor["id"],
            "import_provenance": _provenance(backup, import_run_id, "estimates", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })

    for row in source["estimate_items"]:
        quantity = max(1, _clean_int(row.get("quantity_decimal"), 1))
        collections["quote_line_items"].append({
            "id": ids["estimate_items"][row["id"]],
            "tenant_id": tenant_id,
            "quote_id": ids["estimates"][row["estimate_id"]],
            "revision_number": 1,
            "position": _clean_int(row.get("position"), 0),
            "description": row.get("description") or "Imported line item",
            "quantity": quantity,
            "unit_of_measure": "each",
            "unit_price_cents": _clean_cents(row.get("unit_price_cents")),
            "discount_cents": 0,
            "tax_cents": _clean_cents(row.get("line_total_cents")) - (_clean_cents(row.get("unit_price_cents")) * quantity) if row.get("taxable") else 0,
            "line_subtotal_cents": _clean_cents(row.get("unit_price_cents")) * quantity,
            "line_total_cents": _clean_cents(row.get("line_total_cents")),
            "selected_price_source": "manual",
            "pricing_status": "manual",
            "production_required": bool(row.get("production_required")),
            "notes": row.get("internal_note"),
            "assigned_user_id": map_user(row.get("assigned_user_id"), "estimate_item", row["id"]),
            "import_provenance": _provenance(backup, import_run_id, "estimate_items", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })

    for row in source["orders"]:
        number, mapping = await _number_for_source(tenant_id=tenant_id, record_type="order", source_number=row.get("order_number"), prefix="O", import_run_id=import_run_id, source_id=row["id"], actor=actor)
        sequence_maxima["order"] = max(sequence_maxima["order"], number)
        number_mappings["orders"].append(mapping | {"source_id": row["id"], "target_id": ids["orders"][row["id"]]})
        collections["orders"].append({
            "id": ids["orders"][row["id"]],
            "tenant_id": tenant_id,
            "number": number,
            "customer_id": ids["customers"][row["customer_id"]],
            "quote_id": ids["estimates"].get(row.get("source_estimate_id")),
            "source_quote_id": ids["estimates"].get(row.get("source_estimate_id")),
            "source_type": "slim_import",
            "source_id": f"{import_run_id}:{row['id']}",
            "job_name": f"Imported Slim Order {row.get('order_number') or number}",
            "title": f"Imported Slim Order {row.get('order_number') or number}",
            "notes": row.get("internal_notes"),
            "notes_internal": row.get("internal_notes"),
            "subtotal_cents": _clean_cents(row.get("subtotal_cents")),
            "discount_cents": _clean_cents(row.get("discount_cents")),
            "tax_cents": _clean_cents(row.get("tax_cents")),
            "total_cents": _clean_cents(row.get("total_cents")),
            "amount_paid_cents": 0,
            "balance_cents": _clean_cents(row.get("total_cents")),
            "due_date": row.get("due_date"),
            "status": _map_status(row.get("status"), {"draft", "confirmed", "in_production", "ready", "completed", "cancelled", "archived"}, "confirmed"),
            "created_by": actor["id"],
            "import_provenance": _provenance(backup, import_run_id, "orders", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })

    for row in source["order_items"]:
        quantity = max(1, _clean_int(row.get("quantity_decimal"), 1))
        source_stage = row.get("production_stage") or "not_started"
        if row.get("production_required") and source_stage not in SLIM_STAGE_TO_MVP_STATUS:
            raise SlimImportError("unsupported_production_stage")
        collections["order_items"].append({
            "id": ids["order_items"][row["id"]],
            "tenant_id": tenant_id,
            "order_id": ids["orders"][row["order_id"]],
            "source_type": "slim_import",
            "source_id": f"{import_run_id}:{row['id']}",
            "source_estimate_item_id": ids["estimate_items"].get(row.get("source_estimate_item_id")),
            "position": _clean_int(row.get("position"), 0),
            "description": row.get("description") or "Imported order item",
            "quantity": quantity,
            "unit_of_measure": "each",
            "unit_price_cents": _clean_cents(row.get("unit_price_cents")),
            "discount_cents": 0,
            "tax_cents": _clean_cents(row.get("line_total_cents")) - (_clean_cents(row.get("unit_price_cents")) * quantity) if row.get("taxable") else 0,
            "line_subtotal_cents": _clean_cents(row.get("unit_price_cents")) * quantity,
            "line_total_cents": _clean_cents(row.get("line_total_cents")),
            "selected_price_source": "manual",
            "pricing_status": "manual",
            "production_required": bool(row.get("production_required")),
            "notes": row.get("internal_note"),
            "assigned_user_id": map_user(row.get("assigned_user_id"), "order_item", row["id"]),
            "import_provenance": _provenance(backup, import_run_id, "order_items", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })

    await _build_work_orders(tenant_id, actor, backup, import_run_id, ids, source, collections, number_mappings, sequence_maxima)

    for row in source["invoices"]:
        number, mapping = await _number_for_source(tenant_id=tenant_id, record_type="invoice", source_number=row.get("invoice_number"), prefix="I", import_run_id=import_run_id, source_id=row["id"], actor=actor)
        sequence_maxima["invoice"] = max(sequence_maxima["invoice"], number)
        number_mappings["invoices"].append(mapping | {"source_id": row["id"], "target_id": ids["invoices"][row["id"]]})
        financial_status = _map_status(row.get("payment_status"), {"unpaid", "partial", "paid", "refunded", "voided"}, "unpaid")
        document_status = _map_status(row.get("document_status"), {"draft", "issued", "void"}, "draft")
        collections["invoices"].append({
            "id": ids["invoices"][row["id"]],
            "tenant_id": tenant_id,
            "number": number,
            "order_id": ids["orders"][row["order_id"]],
            "customer_id": ids["customers"][row["customer_id"]],
            "title": f"Imported Slim Invoice {row.get('invoice_number') or number}",
            "status": "paid" if financial_status == "paid" else ("void" if document_status == "void" else "draft"),
            "document_status": document_status,
            "financial_status": financial_status,
            "subtotal_cents": _clean_cents(row.get("subtotal_cents")),
            "discount_cents": _clean_cents(row.get("discount_cents")),
            "tax_cents": _clean_cents(row.get("tax_cents")),
            "fee_cents": 0,
            "total_cents": _clean_cents(row.get("total_cents")),
            "amount_paid_cents": _clean_cents(row.get("amount_paid_cents")),
            "amount_refunded_cents": 0,
            "balance_due_cents": _clean_cents(row.get("balance_due_cents")),
            "due_date": row.get("due_date"),
            "notes": row.get("historical_amount_paid_note"),
            "created_by": actor["id"],
            "import_provenance": _provenance(backup, import_run_id, "invoices", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })
        collections["invoice_line_items"].append({
            "id": _uuid(),
            "tenant_id": tenant_id,
            "invoice_id": ids["invoices"][row["id"]],
            "description": f"Imported invoice total from Slim {row.get('invoice_number') or ''}".strip(),
            "quantity": 1,
            "unit_price_cents": _clean_cents(row.get("subtotal_cents")),
            "position": 0,
            "import_provenance": _provenance(backup, import_run_id, "invoices", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })

    for row in source["calendar_events"]:
        collections["calendar_events"].append({
            "id": ids["calendar_events"][row["id"]],
            "tenant_id": tenant_id,
            "event_type": "production_milestone" if row.get("order_item_id") else "custom",
            "title": row.get("title") or "Imported Slim calendar event",
            "description": row.get("internal_note"),
            "start_at": row.get("start_at"),
            "end_at": row.get("end_at"),
            "all_day": bool(row.get("all_day")),
            "status": _map_status(row.get("status"), {"scheduled", "rescheduled", "canceled", "completed"}, "scheduled"),
            "order_id": ids["orders"].get(row.get("order_id")),
            "order_item_id": ids["order_items"].get(row.get("order_item_id")),
            "assigned_user_id": map_user(row.get("assigned_user_id"), "calendar_event", row["id"]),
            "created_by_user_id": map_user(row.get("created_by_user_id"), "calendar_event", row["id"]) or actor["id"],
            "visibility": "staff",
            "source_type": "slim_import",
            "source_id": f"{import_run_id}:{row['id']}",
            "history": [{"action": "imported_from_slim", "at": _now_iso(), "source_status": row.get("status")}],
            "import_provenance": _provenance(backup, import_run_id, "calendar_events", row["id"]),
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        })

    for attachment in backup.attachments:
        metadata = attachment["metadata"]
        content = base64.b64decode(attachment["content_base64"])
        safe = _safe_filename(metadata.get("original_filename") or "attachment")
        storage_key = storage.build_key(tenant_id, safe)
        file_doc = FileRecord(
            tenant_id=tenant_id,
            storage_key=storage_key,
            original_filename=safe,
            mime_type=metadata["mime_type"],
            size_bytes=len(content),
            uploaded_by=actor["id"],
            visibility="internal",
            sha256=_sha256(content),
        ).model_dump()
        file_doc["id"] = ids["attachments"][metadata["id"]]
        file_doc["import_provenance"] = _provenance(backup, import_run_id, "attachments", metadata["id"])
        file_doc["_content"] = content
        collections["files"].append(file_doc)
        collections["attachments"].append(Attachment(
            tenant_id=tenant_id,
            file_id=file_doc["id"],
            parent_type="order",
            parent_id=ids["orders"][metadata["order_id"]],
            attached_by=actor["id"],
            note=f"Imported from Slim attachment {metadata.get('portable_id')}",
        ).model_dump())

    for source_type, target_type in SOURCE_TO_TARGET_TYPES.items():
        source_rows = [entry["metadata"] for entry in backup.attachments] if source_type == "attachments" else source[source_type]
        id_key = "id"
        for row in source_rows:
            target_id = ids[source_type][row[id_key]]
            collections["slim_import_mappings"].append({
                "id": _uuid(),
                "tenant_id": tenant_id,
                "import_run_id": import_run_id,
                "backup_id": backup.manifest["backup_id"],
                "source_tenant_identifier": backup.manifest["source_tenant_identifier"],
                "source_resource_type": source_type,
                "source_resource_id": row[id_key],
                "source_portable_id": row.get("portable_id"),
                "target_resource_type": target_type,
                "target_resource_id": target_id,
                "mapping_status": "created",
                "warnings": [],
                "errors": [],
                "created_at": _now_iso(),
            })

    return {
        "collections": collections,
        "files": collections["files"],
        "sequence_maxima": sequence_maxima,
        "number_mappings": number_mappings,
        "unassigned_records": unassigned_records,
        "counts": {collection: len(rows) for collection, rows in collections.items()},
    }


async def _build_work_orders(
    tenant_id: str,
    actor: dict[str, Any],
    backup: ValidatedBackup,
    import_run_id: str,
    ids: dict[str, dict[str, str]],
    source: dict[str, list[dict[str, Any]]],
    collections: dict[str, list[dict[str, Any]]],
    number_mappings: dict[str, list[dict[str, Any]]],
    sequence_maxima: dict[str, int],
) -> None:
    customers_by_order = {row["id"]: row["customer_id"] for row in source["orders"]}
    items_by_order: dict[str, list[dict[str, Any]]] = {}
    for item in source["order_items"]:
        if item.get("production_required"):
            items_by_order.setdefault(item["order_id"], []).append(item)
    for source_order_id, items in items_by_order.items():
        allocation = await next_record_number(
            tenant_id=tenant_id,
            record_type="work_order",
            idempotency_key=f"slim-import:{import_run_id}:work_order:{source_order_id}",
            issued_to_entity_type="work_order",
            actor_user_id=actor["id"],
            actor_email=actor["email"],
            reason="slim_backup_import",
        )
        sequence_maxima["work_order"] = max(sequence_maxima["work_order"], allocation.number)
        work_order = WorkOrder(
            tenant_id=tenant_id,
            number=allocation.number,
            order_id=ids["orders"][source_order_id],
            customer_id=ids["customers"][customers_by_order[source_order_id]],
            production_status=SLIM_STAGE_TO_MVP_STATUS.get(items[0].get("production_stage") or "not_started", "released"),
            due_date=items[0].get("due_date"),
            assigned_user_ids=[],
            items_snapshot=[
                {
                    "order_item_id": ids["order_items"][item["id"]],
                    "description": item.get("description") or "Imported production item",
                    "quantity": max(1, _clean_int(item.get("quantity_decimal"), 1)),
                    "unit_price_cents": _clean_cents(item.get("unit_price_cents")),
                    "source_production_stage": item.get("production_stage") or "not_started",
                }
                for item in items
            ],
            created_by=actor["id"],
            internal_notes="Imported from SignGuy Slim production-required items.",
            current_order_key=f"slim-import:{import_run_id}:{source_order_id}",
        ).model_dump()
        work_order["import_provenance"] = _provenance(backup, import_run_id, "orders", source_order_id)
        collections["work_orders"].append(work_order)
        number_mappings["work_orders"].append({"source_id": source_order_id, "target_id": work_order["id"], "target_number": allocation.number, "preserved": False})


def _provenance(backup: ValidatedBackup, import_run_id: str, source_type: str, source_id: str) -> dict[str, Any]:
    return {
        "source": "signguy_slim_backup",
        "import_run_id": import_run_id,
        "backup_id": backup.manifest["backup_id"],
        "source_tenant_identifier": backup.manifest["source_tenant_identifier"],
        "source_type": source_type,
        "source_id": source_id,
    }


async def get_import_report(*, tenant_id: str, import_run_id: str, actor: dict[str, Any]) -> dict[str, Any]:
    _require_owner_admin(actor)
    _assert_actor_can_target(actor, tenant_id)
    run = await db.slim_import_runs.find_one({"tenant_id": tenant_id, "id": import_run_id}, {"_id": 0})
    if not run:
        raise SlimImportError("slim_import_not_found", 404)
    return serialize_doc(run)

"""Branding publication, public lookup, and public asset access."""
from __future__ import annotations

from typing import Any, Optional

from pymongo import ReturnDocument

from ..core.db import db
from ..core.permissions import Perm
from ..core.time_utils import prepare_for_mongo, serialize_doc
from ..models.webstore import WebstoreBrandingPublishedVersion
from . import storage
from .entitlements import has_entitlement
from .webstore_branding_contracts import IMAGE_SLOTS, LIVE_BLOCKING_STATUSES, WEBSTORES_FEATURE_KEY, WebstoreBrandingError
from .webstore_branding_drafts import get_staff_branding
from .webstore_branding_records import _activity, _actor_from_user, _audit, _get_store, _now_iso, _record_for_store, _require_staff_perm
from .webstore_branding_validation import _content_hash, normalize_branding, validation_for_branding

async def _publish_readiness_errors(store: dict, branding: dict[str, Any]) -> list[str]:
    errors = validation_for_branding(store, branding)["errors"][:]
    tenant_id = store["tenant_id"]
    webstore_id = store["id"]
    if not await has_entitlement(tenant_id=tenant_id, feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY):
        errors.append("Webstores entitlement is required before this branding can be published.")
    if store.get("status") in LIVE_BLOCKING_STATUSES:
        errors.append("This Webstore cannot publish branding while it is closed or archived.")
    if not store.get("public_slug"):
        errors.append("This Webstore needs a public slug before branding can be published.")
    if store.get("setup_state") != "setup_complete":
        errors.append("Complete Store Setup before publishing branding.")
    active_count = await db.webstore_products.count_documents(
        {"tenant_id": tenant_id, "webstore_id": webstore_id, "status": "active", "public": True, "selling_price_cents": {"$gt": 0}}
    )
    if active_count <= 0:
        errors.append("Add at least one active public product with a price before publishing branding.")
    if not store.get("launch_packet_id"):
        errors.append("Complete the Webstore launch packet before publishing branding.")
    if not store.get("owner_approved_at"):
        errors.append("Store Owner launch approval is required before publishing branding.")
    if not store.get("terms_fee_acknowledged"):
        errors.append("Acknowledge the Webstore fee terms before publishing branding.")
    if store.get("checkout_enabled") and not store.get("stripe_payment_ready"):
        errors.append("Payment readiness must be connected before publishing a checkout-enabled Webstore.")
    return errors


async def _next_published_version(tenant_id: str, webstore_id: str) -> int:
    doc = await db.counters.find_one_and_update(
        {"tenant_id": tenant_id, "name": f"webstore_branding_version:{webstore_id}"},
        {"$setOnInsert": {"tenant_id": tenant_id, "name": f"webstore_branding_version:{webstore_id}"}, "$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["value"])


async def publish(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    store = await _get_store(user["tenant_id"], webstore_id)
    record = await _record_for_store(store)
    if record.get("status") != "owner_approved":
        raise WebstoreBrandingError("owner_approval_required", "Owner approval is required before this branding can be published.", 409)
    submitted = record.get("submitted_snapshot")
    if not submitted:
        raise WebstoreBrandingError("submitted_branding_required", "Send branding for owner review before publishing.", 409)
    submitted_hash = _content_hash(submitted)
    owner_decision = record.get("owner_decision") or {}
    if owner_decision.get("approved_hash") != submitted_hash or record.get("submitted_hash") != submitted_hash:
        raise WebstoreBrandingError("approved_branding_changed", "The approved branding changed and must be sent for review again.", 409)
    publish_errors = await _publish_readiness_errors(store, submitted)
    if publish_errors:
        raise WebstoreBrandingError("branding_publish_blocked", " ".join(publish_errors), 409)
    version = await _next_published_version(user["tenant_id"], webstore_id)
    version_doc = WebstoreBrandingPublishedVersion(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        version=version,
        branding=submitted,
        content_hash=submitted_hash,
        published_by_user_id=user["id"],
        published_by_email=user.get("email"),
        submitted_at=record.get("submitted_at"),
        owner_approved_at=owner_decision.get("decided_at"),
    ).model_dump()
    await db.webstore_branding_versions.insert_one(prepare_for_mongo(version_doc))
    now = _now_iso()
    await db.webstore_branding_records.update_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id},
        {
            "$set": {
                "status": "published",
                "published_branding": submitted,
                "published_hash": submitted_hash,
                "published_version_id": version_doc["id"],
                "published_at": now,
                "updated_at": now,
            }
        },
    )
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_user(user),
        action="webstore.branding_published",
        summary="Branding published",
        entity_id=record["id"],
    )
    return await get_staff_branding(user, webstore_id)


async def published_branding_for_store(store: dict) -> Optional[dict[str, Any]]:
    version = await db.webstore_branding_versions.find_one(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"]},
        {"_id": 0, "branding": 1},
        sort=[("version", -1)],
    )
    if version and version.get("branding"):
        branding = serialize_doc(version["branding"])
        public_slug = store.get("public_slug")
        if public_slug:
            _attach_public_asset_urls(branding, public_slug)
        return branding
    return None


def _collect_image_file_ids(branding: dict[str, Any]) -> set[str]:
    file_ids: set[str] = set()
    for section, field in IMAGE_SLOTS:
        image = (branding.get(section) or {}).get(field) or {}
        if isinstance(image, dict) and image.get("file_id"):
            file_ids.add(str(image["file_id"]))
    return file_ids


def _attach_public_asset_urls(branding: dict[str, Any], public_slug: str) -> None:
    for section, field in IMAGE_SLOTS:
        image = (branding.get(section) or {}).get(field) or {}
        if isinstance(image, dict) and image.get("file_id"):
            image["url"] = f"/api/public/webstores/{public_slug}/branding-assets/{image['file_id']}"


async def public_branding_asset(slug: str, file_id: str) -> tuple[dict, bytes, str]:
    store = await db.webstores.find_one({"public_slug": slug}, {"_id": 0})
    if not store or store.get("status") != "live":
        raise WebstoreBrandingError("webstore_not_found", "Webstore not found", 404)
    version = await db.webstore_branding_versions.find_one(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"]},
        {"_id": 0, "branding": 1},
        sort=[("version", -1)],
    )
    if not version or file_id not in _collect_image_file_ids(version.get("branding") or {}):
        raise WebstoreBrandingError("branding_asset_not_found", "Branding asset not found", 404)
    doc = await db.webstore_setup_files.find_one(
        {"tenant_id": store["tenant_id"], "webstore_id": store["id"], "id": file_id, "status": {"$ne": "removed"}},
        {"_id": 0},
    )
    if not doc or not doc.get("inline_preview_allowed"):
        raise WebstoreBrandingError("branding_asset_not_found", "Branding asset not found", 404)
    data, content_type = storage.get_bytes(doc["storage_key"])
    return serialize_doc(doc), data, doc.get("detected_content_type") or content_type

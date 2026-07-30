"""Webstores Stage 3 - branding drafts, owner review, and publication."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.db import db
from ..core.permissions import Perm, permissions_for_role
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.webstore import WebstoreBrandingPublishedVersion, WebstoreBrandingRecord
from .activity import record_activity_with_audit
from .entitlements import has_entitlement
from . import storage


BRANDING_STATUSES = {"draft", "waiting_owner_approval", "changes_requested", "owner_approved", "published"}
WEBSTORES_FEATURE_KEY = "webstores"
LIVE_BLOCKING_STATUSES = {"closed", "archived"}
WHOLE_SECTION_PATHS = {
    ("header", "show_header"),
    ("hero", "show_hero"),
    ("catalog_introduction", "show_catalog_area"),
}
ALLOWED_FONTS = {"inter", "system", "serif", "display", "condensed"}
ALLOWED_BUTTON_STYLES = {"square", "slightly_rounded", "rounded"}
ALLOWED_BUTTON_DESTINATIONS = {"catalog", "store_information", "contact", "none"}
LOGO_IMAGE_SLOTS = {
    ("brand_basics", "primary_logo"),
    ("brand_basics", "alternate_logo"),
    ("brand_basics", "favicon"),
}
IMAGE_SLOTS = LOGO_IMAGE_SLOTS | {
    ("brand_basics", "social_image"),
    ("hero", "image"),
    ("store_information", "supporting_image"),
}
WEB_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
LOGO_IMAGE_EXTENSIONS = WEB_IMAGE_EXTENSIONS | {"svg"}
BLOCKED_ARTWORK_EXTENSIONS = {"ai", "eps"}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class WebstoreBrandingError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _now_iso() -> str:
    return utc_now().isoformat()


def _require_staff_perm(user: dict, perm: Perm) -> None:
    if perm.value not in set(permissions_for_role(user.get("role", "staff"))):
        raise WebstoreBrandingError("permission_denied", f"Missing permission: {perm.value}", 403)


def _actor_from_user(user: dict) -> dict:
    return {"type": "staff", "id": user.get("id"), "email": user.get("email")}


def _actor_from_identity(identity: dict) -> dict:
    return {"type": "portal", "id": identity.get("id"), "email": identity.get("email")}


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _store_type_defaults(store_type: str) -> dict[str, Any]:
    if store_type == "b2b":
        return {
            "business_welcome": "",
            "ordering_instructions": "",
            "access_notice": "",
            "fulfillment_summary": "",
        }
    if store_type == "fundraiser":
        return {
            "organization_name": "",
            "campaign_heading": "",
            "campaign_message": "",
            "proceeds_explanation": "",
            "show_goal_progress": False,
            "show_campaign_end_date": True,
        }
    if store_type == "event":
        return {
            "event_display_name": "",
            "event_heading": "",
            "event_message": "",
            "show_event_datetime": True,
            "show_location": True,
            "show_ordering_deadline": True,
            "pickup_instructions": "",
        }
    if store_type == "promotional":
        return {
            "campaign_heading": "",
            "campaign_message": "",
            "offer_wording": "",
            "show_deadline": True,
            "promotion_badge": "",
        }
    if store_type == "employee":
        return {
            "company_welcome": "",
            "employee_ordering_instructions": "",
            "access_notice": "",
            "fulfillment_message": "",
        }
    return {
        "general_welcome": "",
        "about_store": "",
        "shopping_instructions": "",
    }


def default_branding(store: dict) -> dict[str, Any]:
    display_name = store.get("name") or "Webstore"
    return {
        "brand_basics": {
            "display_name": display_name,
            "tagline": store.get("description") or "",
            "primary_logo": {},
            "alternate_logo": {},
            "favicon": {},
            "social_image": {},
            "logo_alt_text": "",
        },
        "colors_fonts": {
            "primary_color": "#0f172a",
            "secondary_color": "#1e293b",
            "accent_color": "#2563eb",
            "page_background_color": "#f8fafc",
            "main_text_color": "#111827",
            "button_background_color": "#2563eb",
            "button_text_color": "#ffffff",
            "heading_font": "inter",
            "body_font": "inter",
            "button_corner_style": "slightly_rounded",
        },
        "header": {
            "show_header": True,
            "display_mode": "name",
            "logo_size": "medium",
            "background_color": "#ffffff",
            "announcement_enabled": False,
            "announcement_text": "",
            "announcement_background_color": "#fef3c7",
            "announcement_text_color": "#92400e",
            "announcement_link_destination": "none",
        },
        "hero": {
            "show_hero": True,
            "image": {},
            "image_focal_position": "center",
            "overlay_color": "#000000",
            "headline": display_name,
            "supporting_text": store.get("description") or "",
            "primary_button_enabled": True,
            "primary_button_label": "Shop products",
            "primary_button_destination": "catalog",
        },
        "store_information": {
            "show_section": True,
            "welcome_heading": f"Welcome to {display_name}",
            "welcome_text": store.get("description") or "",
            "supporting_image": {},
            "store_instructions": "",
            "contact_display": "store",
        },
        "store_type_content": _store_type_defaults(store.get("store_type") or "general"),
        "catalog_introduction": {
            "show_catalog_area": True,
            "heading": "Featured products",
            "introduction": "Product catalog content is managed in a later Webstores stage.",
            "background_color": "#ffffff",
        },
        "footer": {
            "show_footer": True,
            "background_color": "#0f172a",
            "text_color": "#ffffff",
            "display_mode": "store_name",
            "message": "",
            "show_contact": True,
            "show_social_links": False,
            "show_policy_links": False,
            "show_powered_by": True,
        },
    }


def _content_hash(content: dict[str, Any]) -> str:
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean_text(value: Any, *, limit: int = 2000) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _normalize_image(value: Any, *, logo_slot: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    image = {k: value.get(k) for k in {"file_id", "url", "file_name", "content_type", "alt_text", "focal_position"} if value.get(k)}
    name = str(image.get("file_name") or image.get("url") or "").split("?", 1)[0].lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in BLOCKED_ARTWORK_EXTENSIONS:
        raise WebstoreBrandingError(
            "web_ready_image_required",
            "Upload a web-ready JPG, PNG, WebP, or supported logo SVG instead of AI or EPS artwork.",
            400,
        )
    allowed = LOGO_IMAGE_EXTENSIONS if logo_slot else WEB_IMAGE_EXTENSIONS
    if ext and ext not in allowed:
        raise WebstoreBrandingError(
            "image_type_not_supported",
            "Upload a supported web image: JPG, PNG, WebP, or SVG for logos only.",
            400,
        )
    if ext == "svg" and not image.get("file_id"):
        raise WebstoreBrandingError(
            "safe_svg_upload_required",
            "Upload SVG logos through the Webstore file uploader so the existing safe-upload checks can verify the file.",
            400,
        )
    image["alt_text"] = _clean_text(image.get("alt_text"), limit=240)
    return image


def normalize_branding(store: dict, incoming: Optional[dict[str, Any]]) -> dict[str, Any]:
    merged = _deep_merge(default_branding(store), incoming or {})
    basics = merged["brand_basics"]
    basics["display_name"] = _clean_text(basics.get("display_name"), limit=120)
    basics["tagline"] = _clean_text(basics.get("tagline"), limit=180)
    basics["logo_alt_text"] = _clean_text(basics.get("logo_alt_text"), limit=240)
    for section, field in IMAGE_SLOTS:
        merged[section][field] = _normalize_image(merged[section].get(field), logo_slot=(section, field) in LOGO_IMAGE_SLOTS)
    for key in (
        "primary_color",
        "secondary_color",
        "accent_color",
        "page_background_color",
        "main_text_color",
        "button_background_color",
        "button_text_color",
    ):
        value = str(merged["colors_fonts"].get(key) or "").strip()
        merged["colors_fonts"][key] = value if COLOR_RE.match(value) else default_branding(store)["colors_fonts"][key]
    if merged["colors_fonts"].get("heading_font") not in ALLOWED_FONTS:
        merged["colors_fonts"]["heading_font"] = "inter"
    if merged["colors_fonts"].get("body_font") not in ALLOWED_FONTS:
        merged["colors_fonts"]["body_font"] = "inter"
    if merged["colors_fonts"].get("button_corner_style") not in ALLOWED_BUTTON_STYLES:
        merged["colors_fonts"]["button_corner_style"] = "slightly_rounded"
    if merged["hero"].get("primary_button_destination") not in ALLOWED_BUTTON_DESTINATIONS:
        merged["hero"]["primary_button_destination"] = "catalog"
    for section in ("header", "hero", "store_information", "catalog_introduction", "footer"):
        for key, value in list(merged[section].items()):
            if isinstance(value, str):
                merged[section][key] = _clean_text(value, limit=1200)
    for key, value in list(merged["store_type_content"].items()):
        if isinstance(value, str):
            merged["store_type_content"][key] = _clean_text(value, limit=1200)
    return merged


def _luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    channels = [int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    adjusted = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * adjusted[0] + 0.7152 * adjusted[1] + 0.0722 * adjusted[2]


def _contrast_ratio(a: str, b: str) -> float:
    lighter, darker = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def validation_for_branding(store: dict, branding: dict[str, Any]) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    basics = branding.get("brand_basics") or {}
    header = branding.get("header") or {}
    hero = branding.get("hero") or {}
    colors = branding.get("colors_fonts") or {}
    store_type_content = branding.get("store_type_content") or {}
    display_name = _clean_text(basics.get("display_name"))
    if not display_name:
        errors.append("Add a displayed store name before sending this design for approval.")
    if header.get("display_mode") in {"logo", "both"}:
        primary_logo = basics.get("primary_logo") or {}
        if not (primary_logo.get("file_id") or primary_logo.get("url")):
            errors.append("Add a logo before sending this design for approval.")
    for section, field in IMAGE_SLOTS:
        image = (branding.get(section) or {}).get(field) or {}
        if (image.get("file_id") or image.get("url")) and not image.get("alt_text") and field != "favicon":
            errors.append("Add alternate text for every storefront image that will be shown publicly.")
    if hero.get("primary_button_enabled"):
        if not _clean_text(hero.get("primary_button_label"), limit=80):
            errors.append("Add a label for the hero button or turn the button off.")
        if hero.get("primary_button_destination") not in ALLOWED_BUTTON_DESTINATIONS - {"none"}:
            errors.append("Choose a valid destination for the hero button.")
    if _contrast_ratio(colors.get("button_background_color", "#2563eb"), colors.get("button_text_color", "#ffffff")) < 4.5:
        warnings.append("This button text is difficult to read on the selected button color.")
    if _contrast_ratio(colors.get("page_background_color", "#f8fafc"), colors.get("main_text_color", "#111827")) < 4.5:
        warnings.append("This main text is difficult to read on the selected page background color.")
    required_by_type = {
        "b2b": "business_welcome",
        "fundraiser": "campaign_message",
        "event": "event_message",
        "promotional": "campaign_message",
        "employee": "employee_ordering_instructions",
        "general": "general_welcome",
    }
    required_key = required_by_type.get(store.get("store_type") or "general", "general_welcome")
    if not _clean_text(store_type_content.get(required_key)):
        errors.append("Add the required store-type display content before sending this design for approval.")
    return {"errors": errors, "warnings": warnings}


async def _get_store(tenant_id: str, webstore_id: str) -> dict:
    store = await db.webstores.find_one({"tenant_id": tenant_id, "id": webstore_id}, {"_id": 0})
    if not store:
        raise WebstoreBrandingError("webstore_not_found", "Webstore not found", 404)
    return serialize_doc(store)


async def _active_assignment(identity: dict, webstore_id: str) -> dict:
    if identity.get("portal_type") not in {"webstore_owner", "webstore_manager"}:
        raise WebstoreBrandingError("webstore_portal_required", "Webstore portal access required", 403)
    store = await _get_store(identity["tenant_id"], webstore_id)
    assignment = await db.webstore_access_assignments.find_one(
        {
            "tenant_id": identity["tenant_id"],
            "webstore_id": webstore_id,
            "portal_identity_id": identity.get("id"),
            "status": "active",
        },
        {"_id": 0},
    )
    if not assignment:
        raise WebstoreBrandingError("webstore_assignment_scope_forbidden", "Webstore Branding is limited to active assigned stores.", 403)
    role = assignment.get("role")
    if role == "manager" and identity.get("portal_type") != "webstore_manager":
        raise WebstoreBrandingError("webstore_assignment_scope_forbidden", "Webstore manager access is assignment-scoped.", 403)
    if role == "owner" and identity.get("portal_type") != "webstore_owner":
        raise WebstoreBrandingError("webstore_assignment_scope_forbidden", "Webstore owner access is assignment-scoped.", 403)
    return {"store": store, "assignment": serialize_doc(assignment), "role": role}


async def _audit(
    *,
    tenant_id: str,
    webstore_id: str,
    actor: dict,
    action: str,
    summary: str,
    entity_id: str,
    note: Optional[str] = None,
) -> None:
    now = _now_iso()
    activity = {
        "id": f"webstore-branding-activity-{hashlib.sha1(f'{tenant_id}:{webstore_id}:{action}:{entity_id}:{now}'.encode()).hexdigest()}",
        "tenant_id": tenant_id,
        "webstore_id": webstore_id,
        "actor_type": actor["type"],
        "actor_id": actor.get("id"),
        "actor_email": actor.get("email"),
        "action": action,
        "entity_type": "webstore_branding",
        "entity_id": entity_id,
        "summary": summary,
        "metadata": {"note": note} if note else {},
        "created_at": now,
        "updated_at": now,
    }
    await db.webstore_activity_events.insert_one(prepare_for_mongo(activity))
    await record_activity_with_audit(
        tenant_id=tenant_id,
        actor_user_id=actor.get("id") or actor["type"],
        actor_email=actor.get("email") or actor["type"],
        module="webstores",
        action=action,
        entity_type="webstore",
        entity_id=webstore_id,
        summary=summary,
        metadata={"webstore_id": webstore_id, "note": note} if note else {"webstore_id": webstore_id},
    )


async def _record_for_store(store: dict) -> dict:
    record = await db.webstore_branding_records.find_one({"tenant_id": store["tenant_id"], "webstore_id": store["id"]}, {"_id": 0})
    if record:
        return serialize_doc(record)
    draft = normalize_branding(store, store.get("branding") or {})
    record_doc = WebstoreBrandingRecord(
        tenant_id=store["tenant_id"],
        webstore_id=store["id"],
        draft=draft,
        draft_hash=_content_hash(draft),
    ).model_dump()
    try:
        await db.webstore_branding_records.insert_one(prepare_for_mongo(record_doc))
        return serialize_doc(record_doc)
    except DuplicateKeyError:
        existing = await db.webstore_branding_records.find_one({"tenant_id": store["tenant_id"], "webstore_id": store["id"]}, {"_id": 0})
        return serialize_doc(existing)


async def _history(tenant_id: str, webstore_id: str) -> list[dict]:
    return [
        serialize_doc(doc)
        async for doc in db.webstore_branding_versions.find(
            {"tenant_id": tenant_id, "webstore_id": webstore_id},
            {"_id": 0},
        ).sort([("version", -1)])
    ]


async def _activity(tenant_id: str, webstore_id: str) -> list[dict]:
    return [
        serialize_doc(doc)
        async for doc in db.webstore_activity_events.find(
            {
                "tenant_id": tenant_id,
                "webstore_id": webstore_id,
                "action": {
                    "$in": [
                        "webstore.branding_draft_saved",
                        "webstore.branding_review_requested",
                        "webstore.branding_changes_requested",
                        "webstore.branding_owner_approved",
                        "webstore.branding_published",
                    ]
                },
            },
            {"_id": 0},
        ).sort([("created_at", -1)])
    ]


def _response(store: dict, record: dict, *, role: str) -> dict:
    draft = record.get("draft") or default_branding(store)
    return {
        "webstore": {
            "id": store["id"],
            "name": store.get("name"),
            "store_type": store.get("store_type"),
            "status": store.get("status"),
            "setup_state": store.get("setup_state"),
            "public_slug": store.get("public_slug"),
            "public_url": store.get("public_url"),
        },
        "branding": {
            "id": record.get("id"),
            "status": record.get("status") or "draft",
            "draft": draft,
            "draft_hash": _content_hash(draft),
            "submitted_snapshot": record.get("submitted_snapshot"),
            "submitted_hash": record.get("submitted_hash"),
            "owner_decision": record.get("owner_decision") or {},
            "feedback_note": record.get("feedback_note"),
            "published_branding": record.get("published_branding"),
            "published_version_id": record.get("published_version_id"),
            "published_at": record.get("published_at"),
            "validation": validation_for_branding(store, draft),
        },
        "history": [],
        "activity": [],
        "role": role,
        "permissions": {
            "can_save_draft": role in {"staff", "owner", "manager"},
            "can_request_review": role in {"staff", "manager"},
            "can_owner_decide": role == "owner",
            "can_publish": role == "staff",
            "can_control_whole_sections": role == "staff",
        },
    }


async def get_staff_branding(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _get_store(user["tenant_id"], webstore_id)
    record = await _record_for_store(store)
    data = _response(store, record, role="staff")
    data["history"] = await _history(user["tenant_id"], webstore_id)
    data["activity"] = await _activity(user["tenant_id"], webstore_id)
    return data


def _portal_visibility_denied(content: dict[str, Any], current: dict[str, Any]) -> bool:
    for section, field in WHOLE_SECTION_PATHS:
        current_value = (current.get(section) or {}).get(field)
        if section in content and isinstance(content[section], dict) and content[section].get(field) is False and current_value is not False:
            return True
    return False


async def save_staff_draft(user: dict, webstore_id: str, content: dict[str, Any]) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    store = await _get_store(user["tenant_id"], webstore_id)
    record = await _record_for_store(store)
    draft = normalize_branding(store, content)
    draft_hash = _content_hash(draft)
    updates: dict[str, Any] = {"draft": draft, "draft_hash": draft_hash, "updated_at": _now_iso()}
    if record.get("submitted_hash") != draft_hash:
        updates.update({"status": "draft", "submitted_snapshot": None, "submitted_hash": None, "owner_decision": {}})
    await db.webstore_branding_records.update_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id}, {"$set": updates})
    saved = await _record_for_store(store)
    await _audit(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_user(user),
        action="webstore.branding_draft_saved",
        summary="Branding draft saved",
        entity_id=saved["id"],
    )
    return await get_staff_branding(user, webstore_id)


async def get_portal_branding(identity: dict, webstore_id: str) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    record = await _record_for_store(scoped["store"])
    data = _response(scoped["store"], record, role=scoped["role"])
    data["history"] = await _history(identity["tenant_id"], webstore_id)
    data["activity"] = await _activity(identity["tenant_id"], webstore_id)
    return data


async def save_portal_draft(identity: dict, webstore_id: str, content: dict[str, Any]) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    store = scoped["store"]
    record = await _record_for_store(store)
    if _portal_visibility_denied(content, record.get("draft") or default_branding(store)):
        raise WebstoreBrandingError("whole_section_visibility_staff_only", "Only shop staff can hide the entire Header, Hero, or Catalog area.", 403)
    draft = normalize_branding(store, content)
    draft_hash = _content_hash(draft)
    updates: dict[str, Any] = {"draft": draft, "draft_hash": draft_hash, "updated_at": _now_iso()}
    if record.get("submitted_hash") != draft_hash:
        updates.update({"status": "draft", "submitted_snapshot": None, "submitted_hash": None, "owner_decision": {}})
    await db.webstore_branding_records.update_one({"tenant_id": identity["tenant_id"], "webstore_id": webstore_id}, {"$set": updates})
    saved = await _record_for_store(store)
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_identity(identity),
        action="webstore.branding_draft_saved",
        summary="Branding draft saved",
        entity_id=saved["id"],
    )
    return await get_portal_branding(identity, webstore_id)


async def request_review(actor: dict, webstore_id: str, *, portal: bool = False, note: Optional[str] = None) -> dict:
    if portal:
        scoped = await _active_assignment(actor, webstore_id)
        if scoped["role"] != "manager":
            raise WebstoreBrandingError("manager_review_request_required", "Only shop staff or the assigned Store Manager can request owner review.", 403)
        tenant_id = actor["tenant_id"]
        store = scoped["store"]
        audit_actor = _actor_from_identity(actor)
    else:
        _require_staff_perm(actor, Perm.WEBSTORE_WRITE)
        tenant_id = actor["tenant_id"]
        store = await _get_store(tenant_id, webstore_id)
        audit_actor = _actor_from_user(actor)
    record = await _record_for_store(store)
    draft = record.get("draft") or default_branding(store)
    validation = validation_for_branding(store, draft)
    if validation["errors"]:
        raise WebstoreBrandingError("branding_validation_failed", " ".join(validation["errors"]), 409)
    now = _now_iso()
    draft_hash = _content_hash(draft)
    await db.webstore_branding_records.update_one(
        {"tenant_id": tenant_id, "webstore_id": webstore_id},
        {
            "$set": {
                "status": "waiting_owner_approval",
                "submitted_snapshot": draft,
                "submitted_hash": draft_hash,
                "submitted_at": now,
                "submitted_by_actor_type": audit_actor["type"],
                "submitted_by_id": audit_actor.get("id"),
                "submitted_by_email": audit_actor.get("email"),
                "owner_decision": {},
                "feedback_note": None,
                "updated_at": now,
            }
        },
    )
    await _audit(
        tenant_id=tenant_id,
        webstore_id=webstore_id,
        actor=audit_actor,
        action="webstore.branding_review_requested",
        summary="Owner review requested",
        entity_id=record["id"],
        note=note,
    )
    return await (get_portal_branding(actor, webstore_id) if portal else get_staff_branding(actor, webstore_id))


async def owner_approve(identity: dict, webstore_id: str, note: Optional[str] = None) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    if scoped["role"] != "owner":
        raise WebstoreBrandingError("owner_approval_required", "Only the assigned Store Owner can approve branding.", 403)
    record = await _record_for_store(scoped["store"])
    if record.get("status") != "waiting_owner_approval" or not record.get("submitted_snapshot"):
        raise WebstoreBrandingError("branding_review_required", "Send branding for owner review before approval.", 409)
    submitted_hash = _content_hash(record["submitted_snapshot"])
    if submitted_hash != record.get("submitted_hash"):
        raise WebstoreBrandingError("branding_review_changed", "The submitted branding changed and must be sent for review again.", 409)
    now = _now_iso()
    decision = {
        "status": "approved",
        "actor_id": identity.get("id"),
        "actor_email": identity.get("email"),
        "decided_at": now,
        "note": _clean_text(note, limit=1000),
        "approved_hash": submitted_hash,
    }
    await db.webstore_branding_records.update_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id},
        {"$set": {"status": "owner_approved", "owner_decision": decision, "feedback_note": None, "updated_at": now}},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_identity(identity),
        action="webstore.branding_owner_approved",
        summary="Store Owner approved branding",
        entity_id=record["id"],
        note=note,
    )
    return await get_portal_branding(identity, webstore_id)


async def owner_request_changes(identity: dict, webstore_id: str, note: str) -> dict:
    scoped = await _active_assignment(identity, webstore_id)
    if scoped["role"] != "owner":
        raise WebstoreBrandingError("owner_change_request_required", "Only the assigned Store Owner can request branding changes.", 403)
    clean_note = _clean_text(note, limit=1000)
    if not clean_note:
        raise WebstoreBrandingError("feedback_note_required", "Add a change-request note for the shop team.", 400)
    record = await _record_for_store(scoped["store"])
    if record.get("status") != "waiting_owner_approval":
        raise WebstoreBrandingError("branding_review_required", "A submitted branding review is required before requesting changes.", 409)
    now = _now_iso()
    decision = {
        "status": "changes_requested",
        "actor_id": identity.get("id"),
        "actor_email": identity.get("email"),
        "decided_at": now,
        "note": clean_note,
    }
    await db.webstore_branding_records.update_one(
        {"tenant_id": identity["tenant_id"], "webstore_id": webstore_id},
        {"$set": {"status": "changes_requested", "owner_decision": decision, "feedback_note": clean_note, "updated_at": now}},
    )
    await _audit(
        tenant_id=identity["tenant_id"],
        webstore_id=webstore_id,
        actor=_actor_from_identity(identity),
        action="webstore.branding_changes_requested",
        summary="Store Owner requested branding changes",
        entity_id=record["id"],
        note=clean_note,
    )
    return await get_portal_branding(identity, webstore_id)


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

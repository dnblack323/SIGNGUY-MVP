"""Branding normalization, hashing, and validation."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from .webstore_branding_contracts import (
    ALLOWED_BUTTON_DESTINATIONS,
    ALLOWED_BUTTON_STYLES,
    ALLOWED_FONTS,
    BLOCKED_ARTWORK_EXTENSIONS,
    COLOR_RE,
    IMAGE_SLOTS,
    LOGO_IMAGE_EXTENSIONS,
    LOGO_IMAGE_SLOTS,
    WEB_IMAGE_EXTENSIONS,
    WebstoreBrandingError,
)
from .webstore_branding_defaults import _deep_merge, default_branding

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

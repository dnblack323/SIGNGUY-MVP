"""Deterministic staff image preparation, not AI execution or supplier validation."""
from __future__ import annotations

import hashlib
import io
import json
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from ..core.db import db
from ..core.permissions import Perm
from .webstore_shared_access import _require_staff_perm, _require_webstore_assignment_scope
from .webstore_shared_repository import _get_store, _get_product
from .webstore_shared_contracts import WebstoreError
from .webstore_setup_files import WebstoreSetupError, preview_setup_file, store_setup_file
from .webstore_staff_media import create_artwork, create_mockup

SUPPORTED_PRODUCTS = {"t-shirt", "tshirt", "tee", "hoodie"}
MAX_PIXELS = 16_000_000
MAX_INPUT_BYTES = 12 * 1024 * 1024


def _decode(data: bytes) -> Image.Image:
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("Use an image of 12 MB or smaller")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"} or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Use a single-frame PNG, JPEG or WebP image")
            if image.width * image.height > MAX_PIXELS or min(image.size) < 16 or max(image.size) > 6000:
                raise ValueError("Use images between 16 and 6000 pixels per edge, up to 16 megapixels")
            image.load()
            return ImageOps.exif_transpose(image).convert("RGBA")


def _render(blank_data: bytes, artwork_data: bytes, area: dict) -> tuple[bytes, dict]:
    try:
        blank, artwork = _decode(blank_data), _decode(artwork_data)
        left, top = round(area["x"] * blank.width), round(area["y"] * blank.height)
        width, height = round(area["width"] * blank.width), round(area["height"] * blank.height)
        if min(width, height) < 1:
            raise ValueError("The decoration area is too small for this image")
        # Preserve aspect ratio, original colors and alpha; never redraw or recolor branding.
        scale = min(width / artwork.width, height / artwork.height)
        artwork = artwork.resize((max(1, round(artwork.width * scale)), max(1, round(artwork.height * scale))), Image.Resampling.LANCZOS)
        blank.alpha_composite(artwork, (left + (width - artwork.width) // 2, top + (height - artwork.height) // 2))
        output = io.BytesIO()
        blank.info.clear()
        blank.save(output, format="PNG")  # New image, with no source EXIF/text metadata.
        return output.getvalue(), {"output_width": blank.width, "output_height": blank.height}
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise WebstoreError("composition_image_unsupported", str(exc) or "Image cannot be composed; upload a prepared mockup instead", 400) from exc


async def prepare_composition(user: dict, webstore_id: str, product_id: str, fields: dict) -> tuple[bytes, dict, str]:
    _require_staff_perm(user, Perm.WEBSTORE_WRITE)
    await _require_webstore_assignment_scope(user, webstore_id)
    await _get_store(user["tenant_id"], webstore_id)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if product.get("revision", 1) != fields["expected_revision"]:
        raise WebstoreError("revision_conflict", "Product changed. Reload it and prepare a new preview", 409)
    if product.get("status") == "archived":
        raise WebstoreError("product_archived", "Restore the product before preparing a mockup", 409)
    kind = str(product.get("product_type") or "").lower().replace("_", "-").replace(" ", "-")
    if kind not in SUPPORTED_PRODUCTS:
        raise WebstoreError("composition_product_unsupported", "Use a prepared upload for this product. Composition currently supports flat-front T-shirts and hoodies", 409)
    variant = next((v for v in product.get("variants", []) if v.get("id") == fields["variant_id"]), None)
    if not variant or not variant.get("color") or variant.get("status", "active") != "active" or variant.get("available", True) is False:
        raise WebstoreError("composition_variant_unavailable", "Select an active, manually available product variant with a color", 409)
    sources = []
    try:
        for file_id in (fields["blank_file_id"], fields["artwork_file_id"]):
            doc, data, _ = await preview_setup_file(user, webstore_id, file_id)
            generation = doc.get("ai_presentation")
            if generation and (generation.get("review_status") != "accepted" or generation.get("product_id") != product_id
                               or generation.get("variant_id") != variant["id"] or generation.get("color") != variant["color"]):
                raise WebstoreError("presentation_review_required", "Accept a presentation matching this product and variant before composition", 409)
            if doc.get("extension") not in {"png", "jpg", "jpeg", "webp"}:
                raise WebstoreError("composition_format_unsupported", "Use PNG, JPEG or WebP; export SVG/PDF artwork to a transparent PNG or upload a prepared mockup", 400)
            sources.append((doc, data))
    except WebstoreSetupError as exc:
        raise WebstoreError(exc.code, exc.detail, exc.status_code) from exc
    if fields["blank_file_id"] == fields["artwork_file_id"]:
        raise WebstoreError("composition_sources_required", "Select separate blank product and artwork images", 400)
    png, dimensions = await run_in_threadpool(_render, sources[0][1], sources[1][1], fields["placement"])
    provenance = {"method": "original_artwork_composition_v1", "product_revision": fields["expected_revision"],
                  "variant_id": variant["id"], "color": variant["color"], "size": variant.get("size"),
                  "blank_file_id": fields["blank_file_id"], "artwork_file_id": fields["artwork_file_id"],
                  "blank_sha256": hashlib.sha256(sources[0][1]).hexdigest(),
                  "artwork_sha256": hashlib.sha256(sources[1][1]).hexdigest(),
                  "placement": fields["placement"], "blank_match_confirmed_by": user["id"], **dimensions}
    generation = sources[0][0].get("ai_presentation")
    if generation:
        provenance["ai_presentation"] = {key: generation[key] for key in ("model_key", "action_request_id", "sha256")}
    digest = hashlib.sha256(png + json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    return png, provenance, digest


async def save_composition(user: dict, webstore_id: str, product_id: str, fields: dict) -> dict:
    png, provenance, digest = await prepare_composition(user, webstore_id, product_id, fields)
    if fields["preview_sha256"] != digest:
        raise WebstoreError("composition_preview_changed", "Sources or settings changed. Review a fresh preview before saving", 409)
    product = await _get_product(user["tenant_id"], product_id, webstore_id)
    if product.get("revision", 1) != fields["expected_revision"]:
        raise WebstoreError("revision_conflict", "Product changed. Review a fresh preview", 409)
    # Append-only asset identity: never replace the source file or a submitted mockup.
    try:
        file = await store_setup_file(tenant_id=user["tenant_id"], webstore_id=webstore_id,
            actor_type="staff", actor_id=user["id"], filename="product-mockup.png", content_type="image/png",
            data=png, category="mockup", notes="Staff accepted original-artwork composition; no AI execution or credits")
    except WebstoreSetupError as exc:
        raise WebstoreError(exc.code, exc.detail, exc.status_code) from exc
    artwork = await db.webstore_artwork_files.find_one({"tenant_id": user["tenant_id"], "webstore_id": webstore_id,
        "product_id": product_id, "file_id": fields["artwork_file_id"]}, {"_id": 0})
    if not artwork:
        artwork = await create_artwork(user, webstore_id, {"product_id": product_id, "file_id": fields["artwork_file_id"], "purpose": "Original artwork for composition"})
    mockup = await create_mockup(user, webstore_id, {"product_id": product_id, "artwork_id": artwork["id"],
        "mockup_file_id": file["id"], "generation_source": "deterministic_composition", "preparation": provenance,
        "alt_text": fields["alt_text"], "purpose": "Owner product review", "shop_approved": True, "owner_visible": False})
    return {"file": file, "artwork": artwork, "mockup": mockup}

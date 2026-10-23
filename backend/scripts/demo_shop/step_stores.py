"""Webstores: four demonstration stores walked through the real setup workflow to different stages.

Staff actions use the staff API. Store-owner actions (accepting the invitation, submitting the questionnaire,
approving branding / products / mockups / the launch packet) use the real owner-portal endpoints with an owner
session. Emails are disabled, so the owner's invitation link is stood in for by installing a known one-time token
on the pending invitation (the single non-API write besides the Webstores entitlement); nothing is sent anywhere.
Checkout is never enabled and no payment provider is configured: stores stop short of going live.
"""
from __future__ import annotations

from scripts.demo_shop import data_stores as ds
from scripts.demo_shop import step_files
from scripts.demo_shop.client import DemoApi, DemoSeedError
from scripts.demo_shop.step_shop import ensure

TERMS_VERSION = "webstore_terms_2026_07"


async def _grant_entitlement(ctx) -> None:
    """Webstores is a billed feature and the platform has no write API for entitlements yet; the demo shop is simply
    enabled (no subscription, no payment). This is a direct write limited to the demo tenant."""
    from app.core.db import db
    from app.core.time_utils import prepare_for_mongo
    from app.models.feature_entitlement import FeatureEntitlement

    tenant_id = ctx.api.tenant["id"]
    if await db.feature_entitlements.find_one({"tenant_id": tenant_id, "feature_key": "webstores"}):
        return
    ent = FeatureEntitlement(tenant_id=tenant_id, feature_key="webstores", enabled=True, granted_by="demo_seed",
                             notes="Demonstration shop: feature enabled without a subscription.")
    await db.feature_entitlements.insert_one(prepare_for_mongo(ent.model_dump()))
    ctx.note("entitlements", True)


async def _owner_session(ctx, webstore_id: str) -> DemoApi:
    """Accept the pending owner invitation through the real endpoint and return an owner-portal client."""
    from app.core.db import db
    from app.core.portal_security import generate_raw_token, hash_token
    from server import app

    raw = generate_raw_token()
    res = await db.webstore_invitations.update_one({"webstore_id": webstore_id, "status": {"$in": ["pending", "sent"]}}, {"$set": {"token_hash": hash_token(raw)}})
    if res.matched_count != 1:
        raise DemoSeedError(f"No pending owner invitation for webstore {webstore_id}")
    owner = DemoApi(app)
    accepted = await owner.post("/portal/webstores/invitations/accept", {"token": raw})
    owner._http.headers["Authorization"] = f"Bearer {accepted['token']}"
    return owner


async def _setup_file(ctx, webstore_id: str, art_key: str, category: str = "logo") -> dict:
    name, head, sub, bg, fg, _p, _v = step_files.ART[art_key]
    body = await ctx.api.call("POST", f"/webstores/{webstore_id}/setup-files", files={"file": (name, step_files.render(head, sub, bg, fg), "image/png")}, data={"category": category})
    ctx.note("webstore_files", True)
    return body["file"]


def _answers(spec: dict) -> dict:
    name, email, phone = spec["contact"]
    d = ds.dates(spec)
    base = dict(contact_name=name, contact_email=email, contact_phone=phone, target_launch_at=d["target_launch_at"], deadline_at=d["deadline_at"],
                late_orders_allowed="no", repeat_campaign="one_time", open_to_suggestions="yes", intake_acknowledgement=["confirmed"])
    answers = {**base, **spec["answers"]}
    if "pickup_window_count" in answers:
        answers.update(pickup_window_1_date=day_plus(d["target_launch_at"], 14), pickup_window_1_start="15:00", pickup_window_1_end="18:00")
    return answers


def day_plus(iso: str, days: int) -> str:
    from datetime import date, timedelta

    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def _branding_content(spec: dict, logo_file_id: str) -> dict:
    return {"brand_basics": {"display_name": spec["name"].split(" - ")[0], "tagline": spec["purpose"],
                                "primary_logo": {"file_id": logo_file_id, "alt_text": f"{spec['name']} logo"}},
               "header": {"display_mode": "both"},
               "colors_fonts": {"button_background_color": "#B9501A"},
               "store_type_content": {"campaign_message": spec.get("campaign", spec["purpose"]), "general_welcome": f"Welcome to the {spec['name']}.",
                                      "business_welcome": f"Welcome to {spec['name']}.", "event_message": spec["purpose"]}}


async def _branding(ctx, wid: str, spec: dict, logo_file_id: str) -> None:
    content = _branding_content(spec, logo_file_id)
    await ctx.api.call("PATCH", f"/webstores/{wid}/branding/draft", json={"content": content})
    await ctx.api.post(f"/webstores/{wid}/branding/request-review", {"note": "Please review the colors, logo and wording."})


async def _products(ctx, wid: str, kind: str, art_file_id: str, *, approve: bool, owner: DemoApi | None) -> None:
    api = ctx.api
    cat = await api.post(f"/webstores/{wid}/product-categories", {"name": "Apparel & Gear", "description": "Demonstration products"})
    for n, (name, short, long_, ptype, method, cost, price, share, sizes) in enumerate(ds.products(kind)):
        prod = await api.post(f"/webstores/{wid}/products", {
            "name": name, "short_description": short, "full_description": long_, "category_id": cat["id"], "product_type": ptype,
            "production_method": method, "production_cost_cents": cost, "selling_price_cents": price, "store_owner_share_cents": share,
            "fulfillment_methods": ["pickup"], "default_fulfillment_method": "pickup", "pickup_instructions": "Pick up during the listed window.",
            "variants": [{"name": s, "sku": f"{kind[:3].upper()}-{n}-{i}"} for i, s in enumerate(sizes)]})
        ctx.note("webstore_products", True)
        art = await api.post(f"/webstores/{wid}/artwork", {"file_id": art_file_id, "product_id": prod["id"], "purpose": "front_print",
                                                            "file_name": "logo.png", "file_type": "image/png", "notes": "Customer-supplied logo"})
        mock = await api.post(f"/webstores/{wid}/mockups", {"product_id": prod["id"], "artwork_id": art["id"], "mockup_file_id": art_file_id,
                              "generation_source": "manual", "purpose": "storefront", "alt_text": f"{name} mockup", "status": "draft", "shop_approved": approve})
        if not approve:
            continue
        prod = await api.call("PATCH", f"/webstores/{wid}/products/{prod['id']}", json={
            "expected_revision": prod["revision"], "artwork_associations": [{"artwork_id": art["id"]}], "mockup_associations": [{"mockup_id": mock["id"]}],
            "launch_packet_eligible": True, "launch_packet_include": True})
        await api.post(f"/webstores/{wid}/products/{prod['id']}/submit-approval", {"expected_revision": prod["revision"], "comment": "Ready for your review."})
        await owner.post(f"/portal/webstores/{wid}/products/{prod['id']}/approval", {"decision": "approve", "comment": "Looks good."})
        await api.post(f"/webstores/{wid}/mockups/{mock['id']}/submit-approval", {"comment": "Please approve this mockup."})
        await owner.post(f"/portal/webstores/{wid}/mockups/{mock['id']}/approval", {"decision": "approve", "comment": "Great."})


async def webstores(ctx) -> None:
    api = ctx.api
    await _grant_entitlement(ctx)
    await api.put("/webstores/setup/fulfillment-settings", {
        "supported_methods": ["shop_pickup", "organizer_pickup", "individual_shipping", "local_delivery"], "default_pickup_location": "SIGNGUY DEMO SHOP front counter, 100 Commerce Way",
        "pickup_instructions": "Bring your order number. Pick up Monday-Friday, 9am-4pm."})
    existing = {w["name"]: w for w in await api.items("/webstores", limit=200)}
    for spec in ds.STORES:
        if spec["name"] in existing:
            ctx.note("webstores", False)
            ctx.ids[f"webstore:{spec['key']}"] = existing[spec["name"]]["id"]
            continue
        name, email, phone = spec["contact"]
        body = {"customer_id": ctx.ids[f"customer:{spec['customer']}"], "contact": {"name": name, "email": email, "phone": phone},
                "store_type": spec["store_type"], "store_name": spec["name"], "purpose": spec["purpose"], "idempotency_key": spec["request_key"],
                **ds.dates(spec)}
        wid = (await api.post("/webstores/requests", body))["webstore"]["id"]
        ctx.note("webstores", True)
        ctx.ids[f"webstore:{spec['key']}"] = wid
        if spec.get("event_location"):
            await api.patch(f"/webstores/{wid}", {"event_location": spec["event_location"]})
        stage = spec["stage"]
        if stage == "invited":
            continue  # invitation pending; the owner has not started

        owner = await _owner_session(ctx, wid)
        try:
            sub = await owner.post(f"/portal/webstores/{wid}/questionnaire", {"answers": _answers(spec)})
            if stage == "returned_for_changes":
                await api.post(f"/webstores/{wid}/questionnaire/{sub['id']}/return", {"reason": ds.RETURN_REASON})
                await owner.post(f"/portal/webstores/{wid}/questionnaire", {"answers": {**_answers(spec), "notes": spec["resubmit_note"]}})
                continue
            await api.post(f"/webstores/{wid}/questionnaire/{sub['id']}/approve")
            logo = await _setup_file(ctx, wid, spec["logo"])
            await _branding(ctx, wid, spec, logo["id"])
            if stage == "branding_review":
                await _products(ctx, wid, spec["products"], logo["id"], approve=False, owner=None)
                continue
            # stage == "approved": the owner approves branding, products and mockups and accepts the terms; staff generate the launch packet
            await owner.post(f"/portal/webstores/{wid}/branding/approve", {"note": "Looks great."})
            await _products(ctx, wid, spec["products"], logo["id"], approve=True, owner=owner)
            await owner.post(f"/portal/webstores/{wid}/terms/accept", {"terms_version": TERMS_VERSION})
            await api.patch(f"/webstores/{wid}", {"terms_fee_acknowledged": True})
            # The launch packet snapshots the store-level branding, so mirror the approved draft there.
            await api.patch(f"/webstores/{wid}", {"branding": _branding_content(spec, logo["id"])})
            await api.post(f"/webstores/{wid}/launch-packets", {"promotion_copy": f"Support {spec['name']}! {spec['purpose']}.", "share_url": "https://example.com/demo-store"})
            # Delivery to the owner stops here: an owner who accepted an invitation is not yet linked as the store's
            # "verified recipient", so the app refuses to send the packet (reported as a known limitation).
        finally:
            await owner.aclose()

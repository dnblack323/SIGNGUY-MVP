"""Launch readiness response construction for Webstores."""
from __future__ import annotations

from .webstore_shared import *
from .webstore_launch_packet import _included_packet_products
from .webstore_launch_state import _open_change_requests, _payment_readiness, _terms_acceptance

async def launch_readiness(user: dict, webstore_id: str) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_READ)
    store = await _ensure_public_slug(await _get_store(user["tenant_id"], webstore_id))
    owner = await owners_repo.get(tenant_id=user["tenant_id"], entity_id=store["owner_id"])
    packet = await packets_repo.get(tenant_id=user["tenant_id"], entity_id=store["launch_packet_id"]) if store.get("launch_packet_id") else None
    included_products = await _included_packet_products(user["tenant_id"], webstore_id, store.get("public_slug"))
    open_changes = await _open_change_requests(user["tenant_id"], webstore_id)
    questionnaire = await submissions_repo.find_one(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": {"$in": ["submitted", "reviewed"]}}
    )
    terms_version = store.get("required_terms_version") or CURRENT_WEBSTORE_TERMS_VERSION
    terms = await _terms_acceptance(user["tenant_id"], webstore_id, terms_version)
    payment = await _payment_readiness(store)
    type_requirements = evaluate_type_requirements(store)
    branding = await branding_svc.published_branding_for_store(store)
    branding_source = branding or store.get("branding") or {}
    branding_validation = (
        branding_svc.validation_for_branding(store, branding_source)
        if branding_source
        else {"errors": ["Publish owner-safe branding with logo/color/greeting content before launch readiness."], "warnings": []}
    )
    branding_complete = bool(branding_source) and not branding_validation["errors"]
    entitlement_ready = await has_entitlement(tenant_id=user["tenant_id"], feature_key=store.get("entitlement_feature_key") or WEBSTORES_FEATURE_KEY)
    delivered = bool(packet and packet.get("status") in {"delivered", "sent_for_approval", "owner_approved"} and packet.get("id") == store.get("launch_packet_id"))
    approved = bool(
        packet
        and store.get("owner_approved_packet_id") == packet.get("id")
        and store.get("owner_approved_packet_version") == packet.get("version")
        and store.get("owner_approved_at")
        and not store.get("owner_approval_invalidated_at")
        and packet.get("status") == "owner_approved"
    )
    active_public_count = await db.webstore_products.count_documents(
        {"tenant_id": user["tenant_id"], "webstore_id": webstore_id, "status": "active", "public": True, "selling_price_cents": {"$gt": 0}}
    )
    gates = [
        {
            "key": "entitlement",
            "state": "ready" if entitlement_ready else "blocked",
            "reason": "Webstores entitlement is active." if entitlement_ready else "Webstores entitlement is not active.",
            "severity": "blocking",
            "action": "Enable the Webstores feature entitlement.",
            "resource": {"type": "webstore", "id": webstore_id},
            "owner_wording": "The store workspace is not available yet.",
            "blocking": not entitlement_ready,
        },
        {
            "key": "owner_authorized",
            "state": "ready" if owner and owner.get("status") == "active" and owner.get("portal_identity_id") else "blocked",
            "reason": "Store Owner portal recipient is active." if owner and owner.get("status") == "active" and owner.get("portal_identity_id") else "Assign an active Store Owner portal recipient.",
            "severity": "blocking",
            "action": "Create or resend the Store Owner portal invitation.",
            "resource": {"type": "webstore_owner", "id": store.get("owner_id")},
            "owner_wording": "Store Owner access is not ready yet.",
            "blocking": not (owner and owner.get("status") == "active" and owner.get("portal_identity_id")),
        },
        {
            "key": "store_identity",
            "state": "ready" if store.get("name") and store.get("slug") and store.get("public_slug") else "blocked",
            "reason": "Store identity and safe public reference are present." if store.get("name") and store.get("slug") and store.get("public_slug") else "Complete store name, internal slug, and public slug.",
            "severity": "blocking",
            "action": "Complete store setup details.",
            "resource": {"type": "webstore", "id": webstore_id},
            "owner_wording": "Store details are still being prepared.",
            "blocking": not (store.get("name") and store.get("slug") and store.get("public_slug")),
        },
        {
            "key": "questionnaire_complete",
            "state": "ready" if questionnaire else "blocked",
            "reason": "Store Owner questionnaire has been submitted." if questionnaire else "Store Owner questionnaire must be submitted before launch readiness.",
            "severity": "blocking",
            "action": "Send or complete the Webstore questionnaire.",
            "resource": {"type": "webstore_questionnaire_submission", "id": (questionnaire or {}).get("id")},
            "owner_wording": "Store questionnaire answers are still needed.",
            "blocking": not bool(questionnaire),
        },
        {
            "key": "included_products_ready",
            "state": "ready" if included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products) else "blocked",
            "reason": "Included products, product approvals, and mockup approvals are ready for owner review." if included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products) else "Include at least one ready product with price, variants/SKU, customer-facing media, and current product/mockup approvals.",
            "severity": "blocking",
            "action": "Finish Product Setup and packet inclusion.",
            "resource": {"type": "webstore_products", "id": webstore_id},
            "owner_wording": "Products are still being prepared.",
            "blocking": not (included_products and all((p.get("readiness") or {}).get("status") == "ready" for p in included_products)),
        },
        {
            "key": "branding_preview_complete",
            "state": "ready" if branding_complete else "blocked",
            "reason": "Owner-safe branding preview content is complete." if branding_complete else "Complete owner-visible branding display content.",
            "severity": "blocking",
            "action": "Review the Branding tab and complete the owner-safe preview.",
            "resource": {"type": "webstore_branding", "id": webstore_id},
            "owner_wording": "Store branding and welcome content are still being prepared.",
            "blocking": not branding_complete,
            "requirements": branding_validation,
        },
        {
            "key": "packet_generated",
            "state": "ready" if packet else "blocked",
            "reason": f"Launch packet version {packet.get('version')} exists." if packet else "Generate a Launch Packet.",
            "severity": "blocking",
            "action": "Generate the packet from current setup.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Your launch packet is not ready yet.",
            "blocking": not bool(packet),
        },
        {
            "key": "packet_delivered",
            "state": "ready" if delivered else "blocked",
            "reason": "Current packet version was delivered to the Store Owner portal." if delivered else "Deliver the current packet version to the Store Owner.",
            "severity": "blocking",
            "action": "Send the current packet version.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Your launch packet has not been delivered yet.",
            "blocking": not delivered,
        },
        {
            "key": "packet_approved",
            "state": "ready" if approved else "blocked",
            "reason": f"Store Owner approved packet version {packet.get('version')}." if approved else (store.get("owner_approval_invalidated_reason") or "Store Owner approval is required for the current packet version."),
            "severity": "blocking",
            "action": "Have the Store Owner approve the current packet version.",
            "resource": {"type": "webstore_launch_packet", "id": (packet or {}).get("id")},
            "owner_wording": "Approval is still required for the current packet version.",
            "blocking": not approved,
        },
        {
            "key": "terms_current",
            "state": "ready" if terms else "blocked",
            "reason": f"Current Terms version {terms_version} accepted." if terms else f"Store Owner must accept Terms version {terms_version}.",
            "severity": "blocking",
            "action": "Store Owner accepts the current Terms version.",
            "resource": {"type": "webstore_terms_acceptance", "id": (terms or {}).get("id")},
            "owner_wording": "Terms acceptance is still required.",
            "blocking": not bool(terms),
        },
        {
            "key": "change_requests_resolved",
            "state": "ready" if not open_changes else "blocked",
            "reason": "No open Store Owner change requests." if not open_changes else f"{len(open_changes)} owner change request(s) remain open or answered.",
            "severity": "blocking",
            "action": "Respond to and resolve owner change requests.",
            "resource": {"type": "webstore_change_requests", "id": webstore_id},
            "owner_wording": "Requested changes are being reviewed.",
            "blocking": bool(open_changes),
        },
        {
            "key": "type_requirements",
            "state": "ready" if type_requirements["complete"] else "blocked",
            "reason": "Store-type settings and requirements are complete." if type_requirements["complete"] else "Complete required store-type settings before launch.",
            "severity": "blocking",
            "action": "Review the Store Type Rules panel and complete missing settings.",
            "resource": {"type": "webstore_type_requirements", "id": webstore_id},
            "owner_wording": f"{type_requirements['label']} store details are still being completed.",
            "blocking": not type_requirements["complete"],
            "requirements": type_requirements["items"],
        },
        {
            "key": "payment_ready",
            "state": payment["state"],
            "reason": payment["reason"],
            "severity": "advisory",
            "action": "Complete existing payment-readiness prerequisites when available.",
            "resource": {"type": "payment_readiness", "id": webstore_id},
            "owner_wording": "Payment setup is not ready yet.",
            "blocking": False,
            "stage5_deferred": not bool(payment["provider_authority"]),
            "stage7_provider_authority": bool(payment["provider_authority"]),
        },
        {
            "key": "buyer_commerce_connected",
            "state": "ready" if payment["provider_authority"] else "blocked",
            "reason": "Verified provider checkout and webhook reconciliation are connected." if payment["provider_authority"] else payment["reason"],
            "severity": "advisory",
            "action": "Complete Stripe Connect setup and verification before enabling buyer checkout.",
            "resource": {"type": "batch_scope", "id": "batch_3"},
            "owner_wording": "Buyer checkout is available after provider verification.",
            "blocking": False,
            "stage5_deferred": not bool(payment["provider_authority"]),
            "stage7_provider_authority": bool(payment["provider_authority"]),
        },
    ]
    checks = {gate["key"]: not gate["blocking"] for gate in gates}
    checks.update(
        {
            "not_closed_or_archived": store.get("status") not in LIVE_BLOCKING_STATUSES,
            "active_public_products_with_prices": active_public_count > 0,
            "public_branding": branding_complete,
            "questionnaire_complete": bool(questionnaire),
            "launch_packet": bool(packet),
            "owner_approved": approved,
            "terms_fee_acknowledged": bool(terms),
            "payment_ready": bool(payment["ready"]),
            "buyer_commerce_connected": bool(payment["provider_authority"]),
        }
    )
    ready = all(not gate["blocking"] for gate in gates)
    return {
        "webstore_id": webstore_id,
        "ready": ready,
        "checks": checks,
        "gates": gates,
        "current_packet": await _portal_launch_packet_with_history(user["tenant_id"], packet),
        "current_terms_version": terms_version,
        "terms_acceptance": _portal_terms_acceptance(terms),
        "open_change_request_count": len(open_changes),
        "payment_readiness": payment,
        "type_requirements": type_requirements,
        "payment_readiness_source": "provider_boundary",
        "payment_unavailable_reason": payment["reason"],
        "public_launch_blocked_until_batch_3": not bool(payment["provider_authority"]),
    }


async def _compat_launch_readiness(user: dict, webstore_id: str) -> dict:
    import sys

    facade = sys.modules.get(__package__ + ".webstores")
    override = getattr(facade, "launch_readiness", None) if facade is not None else None
    if override is not None and override is not launch_readiness:
        return await override(user, webstore_id)
    return await launch_readiness(user, webstore_id)

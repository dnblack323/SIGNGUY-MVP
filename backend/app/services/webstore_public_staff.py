"""Staff-facing public-storefront report and refund forwarding."""
from __future__ import annotations

from .webstore_shared import *

async def reports(user: dict, webstore_id: str) -> dict:
    from . import webstore_reports

    return await webstore_reports.staff_report(user, webstore_id)


async def refund_webstore_payment(user: dict, webstore_id: str, payment_id: str, fields: dict[str, Any], idempotency_key: Optional[str] = None) -> dict:
    _require_staff_perm(user, Perm.WEBSTORE_MANAGE)
    await _get_store(user["tenant_id"], webstore_id)
    from . import webstore_payments

    return await webstore_payments.initiate_webstore_refund(
        tenant_id=user["tenant_id"],
        webstore_id=webstore_id,
        payment_id=payment_id,
        amount_cents=fields.get("amount_cents"),
        reason=_clean_text(fields.get("reason"), "reason", limit=500),
        actor_user_id=user["id"],
        actor_email=user.get("email") or "",
        idempotency_key=idempotency_key or fields.get("idempotency_key"),
    )

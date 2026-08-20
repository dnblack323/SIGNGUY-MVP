"""Compatibility surface for Webstore payment orchestration.

The implementation lives in responsibility-focused sibling modules. This module
keeps the original import surface and monkeypatch targets stable.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..core.config import get_settings
from ..core.db import db
from ..core.time_utils import prepare_for_mongo, serialize_doc, utc_now
from ..models.customer import Customer
from ..models.order import Order, OrderItem
from ..models.payment import Payment
from ..models.webstore import WebstoreLedgerEntry, WebstorePaymentEvent
from .sequence import next_number, next_record_number
from .webstore_context import WebstoreError
from .webstore_shared import _audit
from .webstore_payment_provider import (
    PAYMENT_PROVIDER_NOT_CONFIGURED,
    ProviderAuthority,
    ProviderFinancialEvent,
    ProviderRefund,
    VerifiedProviderPayment,
    financial_event_from_provider_result,
    get_webstore_payment_provider,
    provider_configuration_status,
    refund_from_provider_result,
)
from .webstore_payments_core import (
    _event_key,
    _event_response,
    _existing_event,
    _now_iso,
    _require_provider_authority,
    _wait_for_terminal_event,
)
from .webstore_payments_events import process_verified_payment_event, reconcile_webstore_payment_status_event
from .webstore_payments_financial import reconcile_webstore_financial_event
from .webstore_payments_handoff import (
    _bridge_to_production,
    _complete_canonical_payment_handoff,
    _create_order_graph,
    _create_payment,
    _customer_for_intent,
    complete_verified_payment_handoff,
)
from .webstore_payments_ledger import _insert_ledger_entry, _record_purchase_ledger
from .webstore_payments_refunds import initiate_webstore_refund, reconcile_webstore_refund_event

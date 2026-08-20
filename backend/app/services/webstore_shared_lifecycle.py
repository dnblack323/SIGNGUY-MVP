"""Focused Webstore shared helpers."""
from __future__ import annotations

from .webstore_context import *

def _validate_transition(current: str, requested: str) -> None:
    if requested not in VALID_WEBSTORE_STATUSES:
        raise WebstoreError("invalid_webstore_status", "Unsupported Webstore lifecycle status", 400)
    if requested == current:
        return
    allowed = WEBSTORE_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise WebstoreError("invalid_webstore_transition", f"Cannot move Webstore from {current} to {requested}", 409)


def _phase6_state_for_status(status: str) -> str:
    return INTERNAL_STATUS_TO_PHASE6.get(status or "draft", "draft")


def _validate_phase6_transition(current: str, requested: str) -> None:
    if requested not in PHASE6_LIFECYCLE_STATES:
        raise WebstoreError("invalid_lifecycle_state", "Unsupported Phase 6 Webstores lifecycle state", 400)
    if requested == current:
        return
    allowed = PHASE6_LIFECYCLE_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise WebstoreError("invalid_lifecycle_transition", f"Cannot move Webstore from {current} to {requested}", 409)


def _validate_status_change(current_status: str, requested_status: str) -> None:
    """Apply the canonical Phase 6 gate plus internal setup-state rules."""
    _validate_transition(current_status, requested_status)
    current_phase = _phase6_state_for_status(current_status)
    requested_phase = _phase6_state_for_status(requested_status)
    if current_phase != requested_phase:
        _validate_phase6_transition(current_phase, requested_phase)

__all__ = [name for name in globals() if not name.startswith("__")]

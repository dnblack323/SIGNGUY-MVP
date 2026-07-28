"""Integer-cent money and rounding contracts for the pure pricing engine."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .validation import ContractValidationError, parse_decimal_string, validate_integer


ROUNDING_POLICY_ID = "pricing_rounding_v1_round_half_up_final_cents"
ROUNDING_MODE = ROUND_HALF_UP


@dataclass(frozen=True, slots=True)
class MoneyCents:
    """Authoritative fixed currency amount stored and serialized as cents."""

    amount_cents: int
    allow_negative: bool = False

    def __post_init__(self) -> None:
        minimum = None if self.allow_negative else 0
        validate_integer(self.amount_cents, field_name="amount_cents", minimum=minimum)

    def to_json(self) -> int:
        return self.amount_cents

    @classmethod
    def nonnegative(cls, amount_cents: Any) -> "MoneyCents":
        return cls(validate_integer(amount_cents, field_name="amount_cents", minimum=0))

    @classmethod
    def signed(cls, amount_cents: Any) -> "MoneyCents":
        return cls(validate_integer(amount_cents, field_name="amount_cents"), allow_negative=True)


@dataclass(frozen=True, slots=True)
class RoundingEvidence:
    policy_id: str = ROUNDING_POLICY_ID
    mode: str = "ROUND_HALF_UP"
    boundary: str = "final_cents"

    def __post_init__(self) -> None:
        if self.policy_id != ROUNDING_POLICY_ID:
            raise ContractValidationError("Unsupported rounding policy")
        if self.mode != "ROUND_HALF_UP":
            raise ContractValidationError("Unsupported rounding mode")
        if self.boundary != "final_cents":
            raise ContractValidationError("Unsupported rounding boundary")

    def to_json(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "mode": self.mode,
            "boundary": self.boundary,
        }


def decimal_dollars_to_cents(value: Any, *, allow_negative: bool = False) -> MoneyCents:
    """Convert a final Decimal dollar component to cents exactly once."""

    decimal_value = parse_decimal_string(value, field_name="dollar_amount")
    if not allow_negative and decimal_value < 0:
        raise ContractValidationError("dollar_amount must be >= 0")
    cents_decimal = (decimal_value * Decimal("100")).quantize(Decimal("1"), rounding=ROUNDING_MODE)
    return MoneyCents.signed(int(cents_decimal)) if allow_negative else MoneyCents.nonnegative(int(cents_decimal))

"""Pure validation helpers for EC9 Phase 9I-J pricing engine contracts."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any


class ContractValidationError(ValueError):
    """Raised when a pricing-engine contract value is invalid."""


def reject_bool(value: Any, *, field_name: str) -> None:
    if isinstance(value, bool):
        raise ContractValidationError(f"{field_name} must not be a boolean")


def validate_integer(
    value: Any,
    *,
    field_name: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    reject_bool(value, field_name=field_name)
    if not isinstance(value, int):
        raise ContractValidationError(f"{field_name} must be an integer")
    if minimum is not None and value < minimum:
        raise ContractValidationError(f"{field_name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ContractValidationError(f"{field_name} must be <= {maximum}")
    return value


def parse_decimal_string(value: Any, *, field_name: str) -> Decimal:
    reject_bool(value, field_name=field_name)
    if isinstance(value, float):
        raise ContractValidationError(f"{field_name} must be a decimal string, not a binary float")
    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ContractValidationError(f"{field_name} must not be blank")
        try:
            decimal_value = Decimal(text)
        except InvalidOperation as exc:
            raise ContractValidationError(f"{field_name} must be a valid decimal string") from exc
    else:
        raise ContractValidationError(f"{field_name} must be a decimal string")
    if not decimal_value.is_finite():
        raise ContractValidationError(f"{field_name} must be finite")
    return decimal_value


def validate_decimal(
    value: Any,
    *,
    field_name: str,
    max_scale: int,
    max_precision: int = 18,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    quantize: bool = True,
) -> Decimal:
    decimal_value = parse_decimal_string(value, field_name=field_name)
    sign, digits, exponent = decimal_value.as_tuple()
    scale = max(0, -exponent)
    integer_digits = max(0, len(digits) - scale)
    if scale > max_scale:
        raise ContractValidationError(f"{field_name} scale must be <= {max_scale}")
    if integer_digits + scale > max_precision:
        raise ContractValidationError(f"{field_name} precision must be <= {max_precision}")
    if minimum is not None and decimal_value < minimum:
        raise ContractValidationError(f"{field_name} must be >= {minimum}")
    if maximum is not None and decimal_value > maximum:
        raise ContractValidationError(f"{field_name} must be <= {maximum}")
    if quantize:
        quantum = Decimal("1").scaleb(-max_scale)
        return decimal_value.quantize(quantum)
    return decimal_value


def decimal_to_string(value: Decimal, *, scale: int) -> str:
    quantum = Decimal("1").scaleb(-scale)
    return format(value.quantize(quantum), f".{scale}f")


def enum_from_value(enum_type: type[Enum], value: Any, *, field_name: str) -> Enum:
    reject_bool(value, field_name=field_name)
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise ContractValidationError(f"{field_name} must be a string identifier")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ContractValidationError(f"Unsupported {field_name}: {value}") from exc


def tuple_of_strings(values: Any, *, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise ContractValidationError(f"{field_name} must be a sequence of strings")
    try:
        normalized = tuple(values)
    except TypeError as exc:
        raise ContractValidationError(f"{field_name} must be a sequence of strings") from exc
    if any(not isinstance(item, str) or not item for item in normalized):
        raise ContractValidationError(f"{field_name} must contain non-empty strings")
    return normalized

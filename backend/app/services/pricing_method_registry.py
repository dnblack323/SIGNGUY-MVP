"""Compatibility exports for EC9 Phase 9I-O pure method registry."""
from pricing_engine import method_registry as _pure_registry
from pricing_engine.method_registry import (  # noqa: F401
    CATEGORY_DEFINITIONS,
    METHOD_DEFINITIONS,
    PRESET_DEFINITIONS,
    available_method_ids_for_context,
    list_category_definitions,
    list_method_definitions,
    list_preset_definitions,
    validate_registry,
)
from pricing_engine.pricing_contracts import PricingContractError as _PurePricingContractError

from .pricing_contracts import PricingContractError


def _translate_contract_error(exc: _PurePricingContractError) -> PricingContractError:
    return PricingContractError(str(exc))


def get_method_definition(method_id: str):
    try:
        return _pure_registry.get_method_definition(method_id)
    except _PurePricingContractError as exc:
        raise _translate_contract_error(exc) from exc


def get_category_definition(category_id: str):
    try:
        return _pure_registry.get_category_definition(category_id)
    except _PurePricingContractError as exc:
        raise _translate_contract_error(exc) from exc


def get_preset_definition(preset_id: str):
    try:
        return _pure_registry.get_preset_definition(preset_id)
    except _PurePricingContractError as exc:
        raise _translate_contract_error(exc) from exc

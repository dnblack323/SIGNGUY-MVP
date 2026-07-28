"""EC9 Phase 9I-A shared pricing contract primitives.

These contracts describe pricing categories, methods, and future tenant method
configuration. They deliberately do not contain pricing formulas or tenant
rates, and they are not wired into live calculation dispatch in Phase 9I-A.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


PRICING_CONTRACT_VERSION = "ec9-9i-a.1"
MAX_COMPARISON_METHODS = 3

class PricingContractError(ValueError):
    """Raised when pricing registry or tenant method configuration is invalid."""


@dataclass(frozen=True)
class PricingMethodDefinition:
    id: str
    display_name: str
    explanation: str
    family: str
    handler_identity: str
    required_configuration_capabilities: tuple[str, ...] = ()
    comparison_eligible: bool = True
    contract_version: str = PRICING_CONTRACT_VERSION
    deprecated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "explanation": self.explanation,
            "family": self.family,
            "handler_identity": self.handler_identity,
            "required_configuration_capabilities": list(self.required_configuration_capabilities),
            "comparison_eligible": self.comparison_eligible,
            "contract_version": self.contract_version,
            "deprecated": self.deprecated,
        }

@dataclass(frozen=True)
class PricingCategoryDefinition:
    id: str
    display_name: str
    family: str
    description: str
    units: tuple[str, ...]
    supported_method_ids: tuple[str, ...]
    recommended_simple_setup_method_ids: tuple[str, ...]
    recommended_primary_method_id: str
    supports_comparison: bool
    max_comparison_methods: int
    configuration_requirements: tuple[str, ...]
    conditional_capability_flags: tuple[str, ...]
    implementation_service: str
    contract_version: str = PRICING_CONTRACT_VERSION
    recommended_starter_values: Mapping[str, Any] = field(default_factory=dict)
    conditional_method_notes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_comparison_methods > MAX_COMPARISON_METHODS:
            raise PricingContractError("Category comparison methods cannot exceed three")
        if self.recommended_primary_method_id not in self.supported_method_ids:
            raise PricingContractError(f"{self.id}: recommended primary method is not supported")
        for method_id in self.recommended_simple_setup_method_ids:
            if method_id not in self.supported_method_ids:
                raise PricingContractError(f"{self.id}: recommended method '{method_id}' is not supported")
        if len(set(self.supported_method_ids)) != len(self.supported_method_ids):
            raise PricingContractError(f"{self.id}: duplicate supported methods")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "family": self.family,
            "description": self.description,
            "units": list(self.units),
            "supported_method_ids": list(self.supported_method_ids),
            "recommended_simple_setup_method_ids": list(self.recommended_simple_setup_method_ids),
            "recommended_primary_method_id": self.recommended_primary_method_id,
            "supports_comparison": self.supports_comparison,
            "max_comparison_methods": self.max_comparison_methods,
            "configuration_requirements": list(self.configuration_requirements),
            "conditional_capability_flags": list(self.conditional_capability_flags),
            "implementation_service": self.implementation_service,
            "contract_version": self.contract_version,
            "recommended_starter_values": dict(self.recommended_starter_values),
            "conditional_method_notes": dict(self.conditional_method_notes),
        }


@dataclass(frozen=True)
class PricingPresetDefinition:
    id: str
    display_name: str
    category_id: str
    supported_method_ids: tuple[str, ...]
    recommended_primary_method_id: str
    supports_comparison: bool = False
    max_comparison_methods: int = 1
    source: str = "pricing_saved_item_starter"
    contract_version: str = PRICING_CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "category_id": self.category_id,
            "supported_method_ids": list(self.supported_method_ids),
            "recommended_primary_method_id": self.recommended_primary_method_id,
            "supports_comparison": self.supports_comparison,
            "max_comparison_methods": self.max_comparison_methods,
            "source": self.source,
            "contract_version": self.contract_version,
        }

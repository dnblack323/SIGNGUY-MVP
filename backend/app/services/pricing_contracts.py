"""EC9 Phase 9I-A shared pricing contract primitives.

These contracts describe pricing categories, methods, and future tenant method
configuration. They deliberately do not contain pricing formulas or tenant
rates, and they are not wired into live calculation dispatch in Phase 9I-A.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping


PRICING_CONTRACT_VERSION = "ec9-9i-a.1"
MAX_COMPARISON_METHODS = 3

ConfigurationMode = Literal["simple", "advanced"]


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


@dataclass(frozen=True)
class TenantCategoryMethodConfiguration:
    tenant_id: str
    category_id: str
    enabled_method_ids: tuple[str, ...]
    primary_method_id: str | None
    comparison_order: tuple[str, ...] = ()
    compare_automatically: bool = False
    configuration_mode: ConfigurationMode = "simple"
    recommended_configuration_version: str = PRICING_CONTRACT_VERSION
    method_configuration_refs: Mapping[str, str] = field(default_factory=dict)
    validation_warnings: tuple[str, ...] = ()
    audit_metadata: Mapping[str, Any] = field(default_factory=dict)
    config_version: str = PRICING_CONTRACT_VERSION

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "TenantCategoryMethodConfiguration":
        return cls(
            tenant_id=str(data.get("tenant_id") or ""),
            category_id=str(data.get("category_id") or ""),
            enabled_method_ids=tuple(data.get("enabled_method_ids") or ()),
            primary_method_id=data.get("primary_method_id"),
            comparison_order=tuple(data.get("comparison_order") or ()),
            compare_automatically=bool(data.get("compare_automatically", False)),
            configuration_mode=data.get("configuration_mode", "simple"),
            recommended_configuration_version=str(data.get("recommended_configuration_version") or PRICING_CONTRACT_VERSION),
            method_configuration_refs=dict(data.get("method_configuration_refs") or {}),
            validation_warnings=tuple(data.get("validation_warnings") or ()),
            audit_metadata=dict(data.get("audit_metadata") or {}),
            config_version=str(data.get("config_version") or PRICING_CONTRACT_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "category_id": self.category_id,
            "enabled_method_ids": list(self.enabled_method_ids),
            "primary_method_id": self.primary_method_id,
            "comparison_order": list(self.comparison_order),
            "compare_automatically": self.compare_automatically,
            "configuration_mode": self.configuration_mode,
            "recommended_configuration_version": self.recommended_configuration_version,
            "method_configuration_refs": dict(self.method_configuration_refs),
            "validation_warnings": list(self.validation_warnings),
            "audit_metadata": dict(self.audit_metadata),
            "config_version": self.config_version,
        }


def _has_duplicates(values: tuple[str, ...]) -> bool:
    return len(set(values)) != len(values)


def validate_tenant_method_configuration(
    config: TenantCategoryMethodConfiguration | Mapping[str, Any],
    category: PricingCategoryDefinition,
) -> TenantCategoryMethodConfiguration:
    """Validate future tenant category-method configuration without persistence.

    The returned object is normalized to stable comparison order. The global
    category/method registry is never mutated.
    """
    cfg = config if isinstance(config, TenantCategoryMethodConfiguration) else TenantCategoryMethodConfiguration.from_mapping(config)
    if not cfg.tenant_id:
        raise PricingContractError("tenant_id is required")
    if cfg.category_id != category.id:
        raise PricingContractError(f"Configuration category '{cfg.category_id}' does not match '{category.id}'")

    enabled = tuple(cfg.enabled_method_ids)
    if _has_duplicates(enabled):
        raise PricingContractError("enabled_method_ids cannot contain duplicates")
    if len(enabled) > MAX_COMPARISON_METHODS:
        raise PricingContractError("No more than three methods can be enabled for comparison")
    unsupported = [method_id for method_id in enabled if method_id not in category.supported_method_ids]
    if unsupported:
        raise PricingContractError(f"Unsupported method(s) for {category.id}: {', '.join(unsupported)}")
    if enabled and not cfg.primary_method_id:
        raise PricingContractError("primary_method_id is required when methods are enabled")
    if cfg.primary_method_id and cfg.primary_method_id not in enabled:
        raise PricingContractError("primary_method_id must be one of the enabled methods")

    order = tuple(cfg.comparison_order or enabled)
    if set(order) != set(enabled) or _has_duplicates(order):
        raise PricingContractError("comparison_order must contain each enabled method exactly once")
    return replace(cfg, enabled_method_ids=enabled, comparison_order=order)


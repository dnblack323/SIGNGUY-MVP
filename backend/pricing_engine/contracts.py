"""EC9 Phase 9I-J immutable contracts for the future shared pricing engine.

These contracts are intentionally unused by production calculators in Phase
9I-J. They define the pure package boundary, explicit units, version metadata,
and JSON-safe numeric representations required by later extraction phases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping

from .money import ROUNDING_POLICY_ID, MoneyCents, RoundingEvidence
from .validation import (
    ContractValidationError,
    decimal_to_string,
    enum_from_value,
    tuple_of_strings,
    validate_decimal,
    validate_integer,
)


CONTRACT_SCHEMA_VERSION = "pricing_contract_schema_9ij_v1"
ENGINE_VERSION = "pricing_engine_contract_foundation_9ij_v1"
FORMULA_VERSION_UNMIGRATED = "legacy_formula_unmigrated_v1"
CATEGORY_CONFIGURATION_VERSION = "category_configuration_contract_9ij_v1"


class CategoryId(StrEnum):
    BANNERS = "banners"
    RIGID_SIGNS = "rigid_signs"
    CUT_VINYL = "cut_vinyl"
    DIGITAL_PRINT = "digital_print"
    VEHICLE_GRAPHICS = "vehicle_graphics"
    APPAREL = "apparel"
    PROMOTIONAL = "promotional"
    SERVICES = "services"
    CUSTOM = "custom"


CATEGORY_IDS: tuple[str, ...] = tuple(category.value for category in CategoryId)


class DimensionUnit(StrEnum):
    INCH = "in"
    FOOT = "ft"


class AreaUnit(StrEnum):
    SQUARE_INCH = "sqin"
    SQUARE_FOOT = "sqft"


class TimeUnit(StrEnum):
    MINUTE = "minute"
    HOUR = "hour"


class QuantityUnit(StrEnum):
    EACH = "each"
    ITEM = "item"
    PIECE = "piece"


class CurrencyRateUnit(StrEnum):
    USD_PER_SQFT = "USD_per_sqft"
    USD_PER_SQIN = "USD_per_sqin"
    USD_PER_HOUR = "USD_per_hour"
    USD_PER_MINUTE = "USD_per_minute"
    USD_PER_EACH = "USD_per_each"


class WasteFactorUnit(StrEnum):
    RATIO = "ratio"
    PERCENT = "percent"


def validate_category_id(value: Any) -> CategoryId:
    return enum_from_value(CategoryId, value, field_name="category_id")  # type: ignore[return-value]


class DecimalValue:
    def as_string(self) -> str:
        return decimal_to_string(self.value, scale=self.scale)


@dataclass(frozen=True, slots=True)
class CurrencyRateDecimal(DecimalValue):
    unit: CurrencyRateUnit
    scale: int = 6

    def __init__(self, value: Any, unit: Any, *, scale: int = 6) -> None:
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="currency_rate",
            max_scale=scale,
            minimum=Decimal("0"),
        ))
        object.__setattr__(self, "unit", enum_from_value(CurrencyRateUnit, unit, field_name="currency_rate_unit"))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> dict[str, str]:
        return {"value": self.as_string(), "unit": self.unit.value}


@dataclass(frozen=True, slots=True)
class PercentDecimal(DecimalValue):
    value: Decimal
    scale: int = 6

    def __init__(self, value: Any, *, minimum: Decimal = Decimal("0"), maximum: Decimal = Decimal("100"), scale: int = 6) -> None:
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="percent_decimal",
            max_scale=scale,
            minimum=minimum,
            maximum=maximum,
        ))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> str:
        return self.as_string()


@dataclass(frozen=True, slots=True)
class BasisPoints:
    value: int
    minimum: int = 0
    maximum: int = 10000

    def __post_init__(self) -> None:
        validate_integer(self.value, field_name="basis_points", minimum=self.minimum, maximum=self.maximum)

    def to_json(self) -> int:
        return self.value

    def as_percent_decimal(self) -> Decimal:
        return Decimal(self.value) / Decimal("100")


@dataclass(frozen=True, slots=True)
class Quantity:
    value: Decimal
    unit: QuantityUnit = QuantityUnit.EACH
    scale: int = 4

    def __init__(self, value: Any, unit: Any = QuantityUnit.EACH, *, scale: int = 4) -> None:
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="quantity",
            max_scale=scale,
            minimum=Decimal("0.0001"),
        ))
        object.__setattr__(self, "unit", enum_from_value(QuantityUnit, unit, field_name="quantity_unit"))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> dict[str, str]:
        return {"value": decimal_to_string(self.value, scale=self.scale), "unit": self.unit.value}


@dataclass(frozen=True, slots=True)
class Dimension:
    value: Decimal
    unit: DimensionUnit
    scale: int = 4

    def __init__(self, value: Any, unit: Any, *, scale: int = 4) -> None:
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="dimension",
            max_scale=scale,
            minimum=Decimal("0.0001"),
        ))
        object.__setattr__(self, "unit", enum_from_value(DimensionUnit, unit, field_name="dimension_unit"))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> dict[str, str]:
        return {"value": decimal_to_string(self.value, scale=self.scale), "unit": self.unit.value}


@dataclass(frozen=True, slots=True)
class Area:
    value: Decimal
    unit: AreaUnit
    scale: int = 4

    def __init__(self, value: Any, unit: Any, *, scale: int = 4) -> None:
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="area",
            max_scale=scale,
            minimum=Decimal("0"),
        ))
        object.__setattr__(self, "unit", enum_from_value(AreaUnit, unit, field_name="area_unit"))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> dict[str, str]:
        return {"value": decimal_to_string(self.value, scale=self.scale), "unit": self.unit.value}


@dataclass(frozen=True, slots=True)
class TimeAmount:
    value: Decimal
    unit: TimeUnit
    scale: int = 4

    def __init__(self, value: Any, unit: Any, *, scale: int = 4) -> None:
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="time_amount",
            max_scale=scale,
            minimum=Decimal("0"),
        ))
        object.__setattr__(self, "unit", enum_from_value(TimeUnit, unit, field_name="time_unit"))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> dict[str, str]:
        return {"value": decimal_to_string(self.value, scale=self.scale), "unit": self.unit.value}


@dataclass(frozen=True, slots=True)
class WasteFactor:
    value: Decimal
    unit: WasteFactorUnit = WasteFactorUnit.RATIO
    scale: int = 6

    def __init__(self, value: Any, unit: Any = WasteFactorUnit.RATIO, *, scale: int = 6) -> None:
        max_value = Decimal("100") if str(unit) == WasteFactorUnit.PERCENT.value else Decimal("10")
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="waste_factor",
            max_scale=scale,
            minimum=Decimal("0"),
            maximum=max_value,
        ))
        object.__setattr__(self, "unit", enum_from_value(WasteFactorUnit, unit, field_name="waste_factor_unit"))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> dict[str, str]:
        return {"value": decimal_to_string(self.value, scale=self.scale), "unit": self.unit.value}


@dataclass(frozen=True, slots=True)
class Markup(DecimalValue):
    value: Decimal
    scale: int = 6

    def __init__(self, value: Any, *, scale: int = 6) -> None:
        object.__setattr__(self, "value", validate_decimal(
            value,
            field_name="markup",
            max_scale=scale,
            minimum=Decimal("0"),
        ))
        object.__setattr__(self, "scale", scale)

    def to_json(self) -> str:
        return self.as_string()


@dataclass(frozen=True, slots=True)
class Margin:
    basis_points: BasisPoints

    def __init__(self, value: Any) -> None:
        object.__setattr__(self, "basis_points", BasisPoints(value, minimum=0, maximum=9999))

    def to_json(self) -> int:
        return self.basis_points.to_json()


@dataclass(frozen=True, slots=True)
class ContractVersionMetadata:
    contract_schema_version: str = CONTRACT_SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION
    formula_version: str = FORMULA_VERSION_UNMIGRATED
    rounding_policy_version: str = ROUNDING_POLICY_ID
    category_configuration_version: str = CATEGORY_CONFIGURATION_VERSION

    def __post_init__(self) -> None:
        if self.contract_schema_version != CONTRACT_SCHEMA_VERSION:
            raise ContractValidationError("Unsupported contract schema version")
        if self.engine_version != ENGINE_VERSION:
            raise ContractValidationError("Unsupported engine version")
        if self.rounding_policy_version != ROUNDING_POLICY_ID:
            raise ContractValidationError("Unsupported rounding policy version")
        if self.category_configuration_version != CATEGORY_CONFIGURATION_VERSION:
            raise ContractValidationError("Unsupported category configuration version")

    def to_json(self) -> dict[str, str]:
        return {
            "contract_schema_version": self.contract_schema_version,
            "engine_version": self.engine_version,
            "formula_version": self.formula_version,
            "rounding_policy_version": self.rounding_policy_version,
            "category_configuration_version": self.category_configuration_version,
        }


@dataclass(frozen=True, slots=True)
class CalculationEvidenceMetadata:
    category_id: CategoryId
    versions: ContractVersionMetadata = field(default_factory=ContractVersionMetadata)
    rounding: RoundingEvidence = field(default_factory=RoundingEvidence)
    formula_source: str = FORMULA_VERSION_UNMIGRATED
    warnings: tuple[str, ...] = ()

    def __init__(
        self,
        category_id: Any,
        *,
        versions: ContractVersionMetadata | None = None,
        rounding: RoundingEvidence | None = None,
        formula_source: str = FORMULA_VERSION_UNMIGRATED,
        warnings: Any = (),
    ) -> None:
        object.__setattr__(self, "category_id", validate_category_id(category_id))
        object.__setattr__(self, "versions", versions or ContractVersionMetadata())
        object.__setattr__(self, "rounding", rounding or RoundingEvidence())
        if not isinstance(formula_source, str) or not formula_source:
            raise ContractValidationError("formula_source must be a non-empty string")
        object.__setattr__(self, "formula_source", formula_source)
        object.__setattr__(self, "warnings", tuple_of_strings(warnings, field_name="warnings"))

    def to_json(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id.value,
            "versions": self.versions.to_json(),
            "rounding": self.rounding.to_json(),
            "formula_source": self.formula_source,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class ContractEnvelope:
    versions: ContractVersionMetadata = field(default_factory=ContractVersionMetadata)
    evidence: CalculationEvidenceMetadata | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"versions": self.versions.to_json()}
        if self.evidence is not None:
            payload["evidence"] = self.evidence.to_json()
        return payload


@dataclass(frozen=True, slots=True)
class CalculationInput(ContractEnvelope):
    category_id: CategoryId = CategoryId.CUSTOM

    def __init__(self, category_id: Any, *, versions: ContractVersionMetadata | None = None) -> None:
        object.__setattr__(self, "versions", versions or ContractVersionMetadata())
        object.__setattr__(self, "evidence", None)
        object.__setattr__(self, "category_id", validate_category_id(category_id))

    def to_json(self) -> dict[str, Any]:
        payload = ContractEnvelope.to_json(self)
        payload["category_id"] = self.category_id.value
        return payload


@dataclass(frozen=True, slots=True)
class CategoryConfiguration(ContractEnvelope):
    category_id: CategoryId = CategoryId.CUSTOM

    def __init__(self, category_id: Any, *, versions: ContractVersionMetadata | None = None) -> None:
        object.__setattr__(self, "versions", versions or ContractVersionMetadata())
        object.__setattr__(self, "evidence", None)
        object.__setattr__(self, "category_id", validate_category_id(category_id))

    def to_json(self) -> dict[str, Any]:
        payload = ContractEnvelope.to_json(self)
        payload["category_id"] = self.category_id.value
        return payload


@dataclass(frozen=True, slots=True)
class LineCalculationResult(ContractEnvelope):
    category_id: CategoryId = CategoryId.CUSTOM
    selling_price: MoneyCents | None = None
    status: str = "not_calculated"

    def __init__(
        self,
        category_id: Any,
        *,
        selling_price: MoneyCents | None = None,
        status: str = "not_calculated",
        versions: ContractVersionMetadata | None = None,
        evidence: CalculationEvidenceMetadata | None = None,
    ) -> None:
        object.__setattr__(self, "versions", versions or ContractVersionMetadata())
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "category_id", validate_category_id(category_id))
        object.__setattr__(self, "selling_price", selling_price)
        if status not in {"not_calculated", "success", "failed", "unavailable"}:
            raise ContractValidationError("Unsupported line calculation status")
        object.__setattr__(self, "status", status)
        if status == "success" and selling_price is None:
            raise ContractValidationError("Successful line result requires selling_price")

    def to_json(self) -> dict[str, Any]:
        payload = ContractEnvelope.to_json(self)
        payload.update({
            "category_id": self.category_id.value,
            "status": self.status,
            "selling_price_cents": self.selling_price.to_json() if self.selling_price else None,
        })
        return payload


@dataclass(frozen=True, slots=True)
class DocumentCalculationInput(ContractEnvelope):
    line_results: tuple[LineCalculationResult, ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentCalculationResult(ContractEnvelope):
    total_cents: MoneyCents | None = None

    def to_json(self) -> dict[str, Any]:
        payload = ContractEnvelope.to_json(self)
        payload["total_cents"] = self.total_cents.to_json() if self.total_cents else None
        return payload


@dataclass(frozen=True, slots=True)
class SnapshotEvidence(ContractEnvelope):
    legacy_readable: bool = True


@dataclass(frozen=True, slots=True)
class SavedCalculation(ContractEnvelope):
    immutable_result: LineCalculationResult | None = None


@dataclass(frozen=True, slots=True)
class PortableConfigExport(ContractEnvelope):
    category_configurations: Mapping[str, CategoryConfiguration] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key, configuration in self.category_configurations.items():
            category = validate_category_id(key)
            if category != configuration.category_id:
                raise ContractValidationError("Configuration key must match category_id")

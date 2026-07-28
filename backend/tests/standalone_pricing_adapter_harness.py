"""EC9 Phase 9I-T test-only standalone pricing adapter harness.

The harness proves the pure pricing engine can run from an explicit portable
configuration outside the SaaS application runtime. It intentionally lives
under tests and imports only pure pricing-engine modules plus the shared
fixture-runner contracts.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from pricing_engine.adapters import build_legacy_line_result
from pricing_engine.config_export import (
    deserialize_portable_configuration,
    validate_portable_configuration,
)
from pricing_engine.line_engine import calculate_line
from pricing_engine.validation import ContractValidationError

from pricing_engine_fixture_runner import (
    AdapterExecutionResult,
    PricingFixture,
    _cents_to_legacy_dollars,
    _dimension_to_legacy_inches,
    _project_cents_first_result_for_fixture,
    _quantity_to_legacy_int,
)


STANDALONE_ADAPTER_ID = "standalone_portable_configuration_adapter_9it_v1"
STANDALONE_ADAPTER_EXECUTION_PATH = (
    "backend.tests.standalone_pricing_adapter_harness.StandalonePricingAdapter.run"
)


class StandalonePricingAdapter:
    """Run shared pricing fixtures through explicit portable configuration."""

    adapter_id = STANDALONE_ADAPTER_ID

    def __init__(self, portable_configuration: Mapping[str, Any]):
        if not isinstance(portable_configuration, Mapping):
            raise ContractValidationError("Standalone portable configuration must be an object")
        self._portable_configuration = validate_portable_configuration(portable_configuration)
        self._deserialized = deserialize_portable_configuration(self._portable_configuration)
        self._validate_engine_settings_by_category()

    @classmethod
    def from_json_file(cls, path: Path) -> "StandalonePricingAdapter":
        payload_path = Path(path)
        try:
            loaded = json.loads(payload_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ContractValidationError(f"{payload_path}: malformed JSON: {exc.msg}") from exc
        if not isinstance(loaded, Mapping):
            raise ContractValidationError("Standalone portable configuration JSON root must be an object")
        return cls(loaded)

    @property
    def portable_configuration(self) -> dict[str, Any]:
        return deepcopy(self._portable_configuration)

    @property
    def engine_settings_by_category(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._deserialized["engine_settings_by_category"])

    def run(self, fixture: PricingFixture) -> AdapterExecutionResult:
        request = fixture.document["normalized_inputs"]["calculator_request"]
        settings = self._deserialized["engine_settings_by_category"].get(fixture.category)
        if settings is None:
            raise ContractValidationError(f"Missing standalone configuration for category {fixture.category!r}")

        raw_result = calculate_line(
            settings=deepcopy(settings),
            category=fixture.category,
            width_inches=_dimension_to_legacy_inches(request.get("width")),
            height_inches=_dimension_to_legacy_inches(request.get("height")),
            quantity=_quantity_to_legacy_int(request["quantity"]),
            material_key=request.get("material_key"),
            design_needed=bool(request.get("design_needed", False)),
            install_needed=bool(request.get("install_needed", False)),
            manual_selling_price=_cents_to_legacy_dollars(request.get("manual_selling_price_cents")),
            category_inputs=deepcopy(request.get("category_inputs") or {}),
            material_profile=deepcopy(request.get("material_profile")),
            pricing_components=deepcopy(request.get("pricing_components") or []),
            saved_item=deepcopy(request.get("saved_item")),
        )
        line_result = build_legacy_line_result(
            category_id=fixture.category,
            legacy_result=raw_result,
            normalized_input=request,
            adapter_source_id=self.adapter_id,
            execution_path=STANDALONE_ADAPTER_EXECUTION_PATH,
        )
        return AdapterExecutionResult(
            adapter_id=self.adapter_id,
            normalized_result=_project_cents_first_result_for_fixture(line_result),
            raw_result={
                "legacy_result": raw_result,
                "pricing_engine_result": line_result,
            },
        )

    def _validate_engine_settings_by_category(self) -> None:
        for category, settings in self._deserialized["engine_settings_by_category"].items():
            if not isinstance(settings.get("shop_defaults"), Mapping):
                raise ContractValidationError(f"{category} standalone engine settings require shop_defaults")
            category_defaults = settings.get("category_defaults")
            if not isinstance(category_defaults, Mapping) or not isinstance(category_defaults.get(category), Mapping):
                raise ContractValidationError(f"{category} standalone engine settings require category_defaults.{category}")
            if not isinstance(settings.get("materials"), Mapping):
                raise ContractValidationError(f"{category} standalone engine settings require materials")

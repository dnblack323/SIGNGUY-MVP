"""Compatibility adapters for the pure pricing-engine contract package."""

from .legacy_result_adapter import (
    LEGACY_RESULT_COMPATIBILITY_DTO_VERSION,
    LEGACY_SAAS_CALCULATOR_SOURCE_ID,
    build_legacy_line_result,
)

__all__ = [
    "LEGACY_RESULT_COMPATIBILITY_DTO_VERSION",
    "LEGACY_SAAS_CALCULATOR_SOURCE_ID",
    "build_legacy_line_result",
]

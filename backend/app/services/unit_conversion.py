"""EC7 phase 7a — Unit conversion for inventory quantities.

Canonical rules:
- Each material carries a `unit_of_measure` (canonical) and a `purchase_unit`.
- Conversions happen at ONE service boundary (this file).
- Preserve original entered unit alongside converted value in movement rows.
- Reject unsupported conversions.
"""
from __future__ import annotations
from typing import Optional


SQIN_PER_SQFT = 144.0
IN_PER_FT = 12.0


def convert_quantity(*, quantity: float, from_unit: str, to_unit: str,
                     material_meta: Optional[dict] = None) -> float:
    """Convert between compatible units. `material_meta` supplies roll/sheet
    dimensions for roll/sheet → area conversions."""
    if from_unit == to_unit:
        return float(quantity)

    # Length
    if {from_unit, to_unit} == {"linear_foot", "linear_inch"}:
        return quantity * IN_PER_FT if to_unit == "linear_inch" else quantity / IN_PER_FT

    # Area
    if {from_unit, to_unit} == {"square_foot", "square_inch"}:
        return quantity * SQIN_PER_SQFT if to_unit == "square_inch" else quantity / SQIN_PER_SQFT

    # Roll → linear_foot / square_foot (requires roll width + length metadata)
    if from_unit == "roll" and to_unit in {"linear_foot", "square_foot"}:
        if not material_meta:
            raise ValueError("unsupported_conversion:roll_requires_material_meta")
        length_ft = material_meta.get("roll_length_feet")
        width_in = material_meta.get("roll_width_inches")
        if not length_ft:
            raise ValueError("unsupported_conversion:missing_roll_length_feet")
        if to_unit == "linear_foot":
            return quantity * float(length_ft)
        if not width_in:
            raise ValueError("unsupported_conversion:missing_roll_width_inches")
        return quantity * float(length_ft) * (float(width_in) / IN_PER_FT)

    # Sheet → square_foot / square_inch
    if from_unit == "sheet" and to_unit in {"square_foot", "square_inch"}:
        if not material_meta:
            raise ValueError("unsupported_conversion:sheet_requires_material_meta")
        w = material_meta.get("sheet_width_inches")
        h = material_meta.get("sheet_height_inches")
        if not (w and h):
            raise ValueError("unsupported_conversion:missing_sheet_dimensions")
        sqin = quantity * float(w) * float(h)
        return sqin if to_unit == "square_inch" else sqin / SQIN_PER_SQFT

    # Package → each (requires quantity_per_package)
    if from_unit == "package" and to_unit == "each":
        if not material_meta or not material_meta.get("quantity_per_package"):
            raise ValueError("unsupported_conversion:missing_quantity_per_package")
        return quantity * float(material_meta["quantity_per_package"])
    if from_unit == "each" and to_unit == "package":
        if not material_meta or not material_meta.get("quantity_per_package"):
            raise ValueError("unsupported_conversion:missing_quantity_per_package")
        qp = float(material_meta["quantity_per_package"])
        return quantity / qp if qp else 0.0

    raise ValueError(f"unsupported_conversion:{from_unit}->{to_unit}")

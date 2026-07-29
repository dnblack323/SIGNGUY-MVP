"""Shared Report Builder export formatting.

All exports consume an already-authorized report result. This module never
queries source collections by itself, which keeps screen/export reconciliation
straightforward and prevents a second reporting engine.
"""
from __future__ import annotations

import html
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from . import csv_export


def _plain(value: Any, column: dict[str, Any]) -> str:
    if value is None:
        return ""
    if column.get("money"):
        try:
            return f"{int(value or 0) / 100:,.2f}"
        except (TypeError, ValueError):
            return ""
    if column.get("date"):
        return str(value)[:10]
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _metadata_lines(result: dict[str, Any], *, export_format: str) -> list[str]:
    return [
        f"Report: {result.get('title') or result.get('key') or result.get('dataset')}",
        f"Format: {export_format}",
        f"Date basis: {result.get('date_basis', 'n/a')}",
        f"Calculation basis: {result.get('calc_basis', 'n/a')}",
        f"Rows: {result.get('row_count', len(result.get('rows') or []))}",
        f"Filters: {result.get('filters') or {}}",
    ]


def _xlsx_cell(value: str, cell_ref: str) -> str:
    return f'<c r="{cell_ref}" t="inlineStr"><is><t>{html.escape(value)}</t></is></c>'


def _xlsx_col(index: int) -> str:
    label = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        label = chr(65 + rem) + label
    return label


def _minimal_xlsx(*, result: dict[str, Any], columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> bytes:
    sheet_rows: list[list[str]] = [[line] for line in _metadata_lines(result, export_format="xlsx")]
    sheet_rows.append([])
    sheet_rows.append([c["label"] for c in columns])
    for row in rows[:25000]:
        sheet_rows.append([_plain(row.get(c["key"]), c) for c in columns])
    xml_rows = []
    for r_index, row in enumerate(sheet_rows, start=1):
        cells = [_xlsx_cell(str(value), f"{_xlsx_col(c_index)}{r_index}") for c_index, value in enumerate(row)]
        xml_rows.append(f'<row r="{r_index}">{"".join(cells)}</row>')
    sheet_xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return stream.getvalue()


def _minimal_pdf(*, result: dict[str, Any], columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> bytes:
    lines = _metadata_lines(result, export_format="pdf")
    lines.append(" | ".join(c["label"] for c in columns))
    for row in rows[:100]:
        lines.append(" | ".join(_plain(row.get(c["key"]), c) for c in columns))
    text = "\\n".join(lines).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 9 Tf 36 560 Td ({text}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 792 612] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('latin-1', errors='ignore'))} >> stream\n{stream}\nendstream endobj",
    ]
    body = "%PDF-1.4\n" + "\n".join(objects) + "\n"
    offsets = []
    cursor = len("%PDF-1.4\n")
    for obj in objects:
        offsets.append(cursor)
        cursor += len((obj + "\n").encode("latin-1", errors="ignore"))
    xref_start = len(body.encode("latin-1", errors="ignore"))
    xref = ["xref", f"0 {len(objects) + 1}", "0000000000 65535 f "]
    xref.extend(f"{offset:010d} 00000 n " for offset in offsets)
    trailer = f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref_start}\n%%EOF"
    return (body + "\n".join(xref) + "\n" + trailer).encode("latin-1", errors="ignore")


def build_export(*, result: dict[str, Any], export_format: str) -> tuple[bytes, str, str]:
    columns = result.get("columns") or [
        {"key": key, "label": key, "money": key.endswith("_cents")}
        for key in (result.get("fields") or [])
    ]
    rows = result.get("rows") or []
    safe_key = (result.get("key") or result.get("dataset") or "report").replace(".", "_")

    if export_format == "csv":
        text = csv_export.build_csv(columns=columns, rows=rows, max_rows=25000)
        return text.encode("utf-8-sig"), "text/csv; charset=utf-8", f"{safe_key}_{export_format}.csv"

    if export_format in {"accounting_csv", "payroll_csv", "tax_csv"}:
        raise ValueError("specialized_export_not_implemented")

    if export_format == "xlsx":
        return (
            _minimal_xlsx(result=result, columns=columns, rows=rows),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{safe_key}.xlsx",
        )

    if export_format == "pdf":
        return _minimal_pdf(result=result, columns=columns, rows=rows), "application/pdf", f"{safe_key}.pdf"

    if export_format == "print":
        lines = _metadata_lines(result, export_format=export_format)
        lines.append("")
        lines.append("\t".join(c["label"] for c in columns))
        for row in rows[:25000]:
            lines.append("\t".join(_plain(row.get(c["key"]), c) for c in columns))
        return "\n".join(lines).encode("utf-8"), "text/plain; charset=utf-8", f"{safe_key}_print.txt"

    raise ValueError("unsupported_export_format")

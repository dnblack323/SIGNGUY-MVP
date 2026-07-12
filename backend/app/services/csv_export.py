"""EC7 phase 7d — CSV export foundation.

Rules (LOCKED):
  - Cells beginning with '=' '+' '-' '@' are prefixed with a single quote to
    neutralize spreadsheet formula-injection.
  - Money cells stored as `_cents` are formatted to two-decimal dollars.
  - Booleans -> "yes"/"no". Nulls -> "".
  - Newlines and quotes inside strings are properly CSV-quoted.
  - Header row includes stable column keys via the report definition.
  - Every export runs behind the same permission the report requires.
  - Max 25 000 rows to prevent unbounded exports.
"""
from __future__ import annotations
import csv
import io
from typing import Any


_UNSAFE_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    s = str(value)
    if s and s[0] in _UNSAFE_PREFIXES:
        s = "'" + s                                     # neutralize formula injection
    return s


def _format_money(cents: Any) -> str:
    try:
        n = int(cents or 0)
    except (TypeError, ValueError):
        return ""
    dollars = n / 100.0
    return f"{dollars:,.2f}"


def build_csv(*, columns: list[dict], rows: list[dict],
              max_rows: int = 25000) -> str:
    """Return CSV text with a header row + at most `max_rows` data rows."""
    if len(rows) > max_rows:
        rows = rows[:max_rows]
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow([c["label"] for c in columns])
    for r in rows:
        row_out: list[str] = []
        for c in columns:
            v = r.get(c["key"])
            if c.get("money"):
                row_out.append(_sanitize_cell(_format_money(v)))
            else:
                row_out.append(_sanitize_cell(v))
        writer.writerow(row_out)
    return buf.getvalue()

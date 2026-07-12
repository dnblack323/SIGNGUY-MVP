"""EC8 phase 8b — tenant-timezone-aware business-date / Saturday-Friday week
boundary helpers.

Timezone is read from the existing Settings store (`company_profile` /
`timezone`, EC2 — read-only here, not modified) so week boundaries never rely
on the browser's local date. Falls back to "America/New_York" if unset.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import settings as settings_service

DEFAULT_TZ = "America/New_York"


async def get_tenant_timezone(tenant_id: str) -> str:
    row = await settings_service.get_setting(tenant_id=tenant_id, namespace="company_profile", key="timezone")
    tz_name = row["value"] if row and row.get("value") else DEFAULT_TZ
    try:
        ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return DEFAULT_TZ


def business_date(dt: datetime, tz_name: str) -> str:
    """Convert a UTC-aware datetime to the tenant-local calendar date (YYYY-MM-DD)."""
    local = dt.astimezone(ZoneInfo(tz_name))
    return local.date().isoformat()


def week_bounds(d: date) -> tuple[date, date]:
    """Saturday-start, Friday-end week containing `d`."""
    days_since_saturday = (d.weekday() - 5) % 7
    start = d - timedelta(days=days_since_saturday)
    end = start + timedelta(days=6)
    return start, end


def week_bounds_for_date_str(date_str: str) -> tuple[str, str]:
    start, end = week_bounds(date.fromisoformat(date_str))
    return start.isoformat(), end.isoformat()


def month_bounds_for_date_str(date_str: str) -> tuple[str, str]:
    d = date.fromisoformat(date_str)
    start = d.replace(day=1)
    if d.month == 12:
        end = d.replace(day=31)
    else:
        end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()

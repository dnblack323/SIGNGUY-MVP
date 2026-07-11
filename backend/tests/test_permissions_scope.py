"""EC1 — Permission Scope Separation Tests.

Verifies that staff Perm, PlatformPerm, and PortalPerm scopes are disjoint
and that the helper functions correctly identify each scope.
"""
from __future__ import annotations

from app.core.permissions import (
    Perm,
    PlatformPerm,
    PortalPerm,
    STAFF_PERMS,
    OWNER_ADMIN_PERMS,
    is_platform_perm,
    is_portal_perm,
    is_staff_perm,
    permissions_for_role,
)


def test_scopes_are_disjoint():
    staff = {p.value for p in Perm}
    platform = {p.value for p in PlatformPerm}
    portal = {p.value for p in PortalPerm}
    assert staff & platform == set()
    assert staff & portal == set()
    assert platform & portal == set()


def test_scope_predicates():
    assert is_staff_perm(Perm.CUSTOMER_READ.value)
    assert not is_staff_perm(PlatformPerm.PLATFORM_ADMIN.value)
    assert not is_staff_perm(PortalPerm.PORTAL_CUSTOMER_VIEW.value)

    assert is_platform_perm(PlatformPerm.PLATFORM_ADMIN.value)
    assert not is_platform_perm(Perm.CUSTOMER_READ.value)
    assert not is_platform_perm(PortalPerm.PORTAL_CUSTOMER_VIEW.value)

    assert is_portal_perm(PortalPerm.PORTAL_CUSTOMER_VIEW.value)
    assert not is_portal_perm(Perm.CUSTOMER_READ.value)
    assert not is_portal_perm(PlatformPerm.PLATFORM_ADMIN.value)


def test_owner_still_has_working_mvp_perms():
    owner_perms = permissions_for_role("owner")
    # All working MVP perms must remain available to Owner.
    for value in [
        "customer:read", "customer:write",
        "quote:read", "quote:write", "quote:convert",
        "order:read", "order:write",
        "work_order:read", "work_order:write",
        "invoice:read", "invoice:write", "payment:write",
        "document:read", "document:write",
        "email:read", "email:send",
        "audit:read",
        "dashboard:read",
        "pricing:read", "pricing:calculate",
    ]:
        assert value in owner_perms, value


def test_staff_role_matches_preserved_mvp_shape():
    staff = set(permissions_for_role("staff"))
    for v in STAFF_PERMS:
        assert v in staff


def test_owner_contains_all_perms():
    assert set(OWNER_ADMIN_PERMS) == {p.value for p in Perm}


def test_platform_scope_not_satisfiable_by_role_map():
    # No standard tenant role should grant platform permissions.
    for role in ("owner", "admin", "staff"):
        for pv in {p.value for p in PlatformPerm}:
            assert pv not in permissions_for_role(role), (role, pv)


def test_portal_scope_not_satisfiable_by_role_map():
    for role in ("owner", "admin", "staff"):
        for pv in {p.value for p in PortalPerm}:
            assert pv not in permissions_for_role(role), (role, pv)

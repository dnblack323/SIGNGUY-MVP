"""Compatibility facade for the Webstores service layer.

The implementation is split across focused Webstore service modules. Import this
module from existing routers/tests to keep the historical public service surface.
"""
from __future__ import annotations

from .webstore_context import *
from .webstore_shared import *
from .webstore_payment_boundary import *
from .webstore_launch import *
from .webstore_staff import *
from .webstore_public import *
from .webstore_owner_portal_service import *

__all__ = [name for name in globals() if not name.startswith("__")]

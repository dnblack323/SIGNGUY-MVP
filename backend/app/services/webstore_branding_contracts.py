"""Branding contracts, constants, and errors for Webstores."""
from __future__ import annotations

import re

BRANDING_STATUSES = {"draft", "waiting_owner_approval", "changes_requested", "owner_approved", "published"}
WEBSTORES_FEATURE_KEY = "webstores"
LIVE_BLOCKING_STATUSES = {"closed", "archived"}
WHOLE_SECTION_PATHS = {
    ("header", "show_header"),
    ("hero", "show_hero"),
    ("catalog_introduction", "show_catalog_area"),
}
ALLOWED_FONTS = {"inter", "system", "serif", "display", "condensed"}
ALLOWED_BUTTON_STYLES = {"square", "slightly_rounded", "rounded"}
ALLOWED_BUTTON_DESTINATIONS = {"catalog", "store_information", "contact", "none"}
LOGO_IMAGE_SLOTS = {
    ("brand_basics", "primary_logo"),
    ("brand_basics", "alternate_logo"),
    ("brand_basics", "favicon"),
}
IMAGE_SLOTS = LOGO_IMAGE_SLOTS | {
    ("brand_basics", "social_image"),
    ("hero", "image"),
    ("store_information", "supporting_image"),
}
WEB_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
LOGO_IMAGE_EXTENSIONS = WEB_IMAGE_EXTENSIONS | {"svg"}
BLOCKED_ARTWORK_EXTENSIONS = {"ai", "eps"}
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class WebstoreBrandingError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)

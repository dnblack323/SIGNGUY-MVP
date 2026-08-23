"""Guard the MVP pricing engine consumer against embedded-engine fallback."""
from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pricing_engine


REPO_ROOT = Path(__file__).resolve().parents[2]
EMBEDDED_ENGINE_DIR = REPO_ROOT / "backend" / "pricing_engine"
EXPECTED_DISTRIBUTION = "signguy-pricing-engine"
EXPECTED_VERSION = "0.1.0"


def test_pricing_engine_is_pinned_external_package():
    assert importlib.metadata.version(EXPECTED_DISTRIBUTION) == EXPECTED_VERSION
    assert pricing_engine.__version__ == EXPECTED_VERSION

    import_path = Path(pricing_engine.__file__).resolve()
    assert not EMBEDDED_ENGINE_DIR.exists()
    assert not import_path.is_relative_to(EMBEDDED_ENGINE_DIR)
    assert "site-packages" in import_path.parts or "dist-packages" in import_path.parts

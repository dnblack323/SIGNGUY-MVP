from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SCANNED_PATHS = [
    ROOT / "backend" / "app",
    ROOT / "backend" / "scripts",
    ROOT / "backend" / "requirements.txt",
    ROOT / "frontend" / "public",
    ROOT / "frontend" / "src",
    ROOT / "frontend" / "package.json",
    ROOT / "frontend" / "yarn.lock",
    ROOT / "frontend" / "craco.config.js",
]

BLOCKED_TERMS = (
    "assets.emergent",
    "auth.emergent",
    "customer-assets.emergent",
    "integrations.emergent",
    "@emergentbase",
    "EMERGENT_LLM_KEY",
    "sk_test_emergent",
)

ALLOWED_FILES = {
    ROOT / "backend" / "app" / "core" / "terminology_guard.py",
}


def test_runtime_code_and_manifests_do_not_depend_on_retired_provider_assets():
    hits: list[str] = []
    for root in SCANNED_PATHS:
        files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in files:
            if path in ALLOWED_FILES or any(part in {"node_modules", "build", "__pycache__"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for term in BLOCKED_TERMS:
                if term in text:
                    hits.append(f"{path.relative_to(ROOT)} contains {term}")
    assert hits == []

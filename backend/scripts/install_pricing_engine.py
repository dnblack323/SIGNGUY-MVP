"""Install the pinned private SignGuy pricing engine wheel.

This script intentionally avoids authenticated URLs in committed files. It uses
PRICING_ENGINE_READ_TOKEN in CI and falls back to the authenticated GitHub CLI
for authorized local developers.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
LOCK_PATH = BACKEND_ROOT / "pricing_engine_package.lock.json"
TOKEN_ENV = "PRICING_ENGINE_READ_TOKEN"


def _load_lock() -> dict[str, str]:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def _auth_token() -> str:
    token = os.environ.get(TOKEN_ENV)
    if token:
        return token
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            text=True,
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        result = None
    if result and result.stdout.strip():
        return result.stdout.strip()
    raise SystemExit(
        f"{TOKEN_ENV} is required. Use a fine-grained GitHub token with read-only "
        "Contents access limited to dnblack323/SIGNGUY-PRICING-ENGINE."
    )


def _request_json(url: str, token: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"GitHub API request failed for {url}: HTTP {exc.code}") from exc


def _download_asset(asset_url: str, destination: Path, token: str) -> None:
    request = urllib.request.Request(
        asset_url,
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            destination.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"GitHub release asset download failed: HTTP {exc.code}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _assert_external_import(import_name: str, package: str, version: str) -> Path:
    installed = importlib.metadata.version(package)
    if installed != version:
        raise SystemExit(f"{package} version mismatch: expected {version}, got {installed}")
    module = __import__(import_name)
    import_path = Path(module.__file__).resolve()
    embedded_source = BACKEND_ROOT / import_name
    if import_path.is_relative_to(embedded_source):
        raise SystemExit(f"{import_name} imported from embedded MVP source tree: {import_path}")
    if "site-packages" not in import_path.parts and "dist-packages" not in import_path.parts:
        raise SystemExit(f"{import_name} did not import from an installed package location: {import_path}")
    return import_path


def main() -> None:
    lock = _load_lock()
    token = _auth_token()
    api_url = f"https://api.github.com/repos/{lock['repository']}/releases/tags/{lock['release_tag']}"
    release = _request_json(api_url, token)
    assets = release.get("assets") or []
    asset = next((item for item in assets if item.get("name") == lock["asset"]), None)
    if not asset:
        raise SystemExit(f"Release asset not found: {lock['asset']}")

    with tempfile.TemporaryDirectory(prefix="signguy-pricing-engine-") as temp_dir:
        wheel = Path(temp_dir) / lock["asset"]
        _download_asset(asset["url"], wheel, token)
        digest = _sha256(wheel)
        expected = lock["sha256"].upper()
        if digest != expected:
            raise SystemExit(f"Wheel SHA256 mismatch: expected {expected}, got {digest}")
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", str(wheel)], check=True)

    import_path = _assert_external_import(lock["import_name"], lock["package"], lock["version"])
    print(f"Installed {lock['package']}=={lock['version']}")
    print(f"Verified wheel SHA256 {lock['sha256'].upper()}")
    print(f"Imported {lock['import_name']} from {import_path}")


if __name__ == "__main__":
    main()

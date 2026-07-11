"""pytest configuration for backend tests."""
import sys
from pathlib import Path

# Ensure app package is importable when running from /app/backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Re-export EC2 async fixtures so pytest auto-discovers them.
from tests.conftest_ec2 import clean_db, seeded_users, _ensure_indexes_once  # noqa: E402, F401

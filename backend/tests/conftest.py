"""pytest configuration for backend tests."""
import os
import sys
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PYTEST_TEMP_ROOT = BACKEND_ROOT.parent / ".pytest_tmp_root"
PYTEST_TEMP_ROOT.mkdir(exist_ok=True)

# Tests must not inherit development or production database settings. These
# values are loaded before any app.core.db import creates the Motor client.
os.environ["ENV"] = "test"
os.environ["AUTH_DEV_BYPASS"] = os.environ.get("TEST_AUTH_DEV_BYPASS", "true")
os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(PYTEST_TEMP_ROOT))
os.environ["MONGO_URL"] = os.environ.get("TEST_MONGO_URL", "mongodb://localhost:27017")
os.environ["DB_NAME"] = os.environ.get(
    "TEST_DB_NAME",
    f"signguy_test_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}_{uuid.uuid4().hex[:8]}",
)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-production-32chars")
os.environ.setdefault("SENDGRID_WEBHOOK_ENABLED", "false")
os.environ.setdefault("STRIPE_WRITES_ENABLED", "false")
os.environ.setdefault("STRIPE_WEBHOOK_ENABLED", "false")
os.environ.setdefault("AI_ENABLED", "false")
os.environ.setdefault("OPENAI_REALTIME_ENABLED", "false")
os.environ.setdefault("SMS_ENABLED", "false")

# Ensure app package is importable when running from /app/backend
sys.path.insert(0, str(BACKEND_ROOT))

# Re-export EC2 async fixtures so pytest auto-discovers them.
from tests.conftest_ec2 import clean_db, seeded_users, _ensure_indexes_once  # noqa: E402, F401

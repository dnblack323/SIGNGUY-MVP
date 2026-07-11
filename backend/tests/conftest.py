"""pytest configuration for backend tests."""
import sys
from pathlib import Path

# Ensure app package is importable when running from /app/backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

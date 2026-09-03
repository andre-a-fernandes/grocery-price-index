"""Shared fixtures: force a deterministic app config before `main` is imported,
so tests never depend on a developer's local backend/.env (e.g. a real APP_SECRET)."""

import os
import sys
from pathlib import Path

# Make `core` / `config` importable the same way main.py imports them,
# regardless of where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force a clean, known configuration before main.py and 'load_dotenv()' are imported
os.environ["APP_SECRET"] = ""
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
os.environ["MAX_UPLOAD_MB"] = "8"
os.environ["RATE_LIMIT_MAX_REQUESTS"] = "20"
os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "3600"

import pytest
from fastapi.testclient import TestClient

from main import _request_log, app


@pytest.fixture(autouse=True)
def clean_rate_log():
    """Start every test with an empty in-memory rate-limit log."""
    _request_log.clear()
    yield
    _request_log.clear()


@pytest.fixture
def client():
    """TestClient with auth disabled (APP_SECRET unset at import time)."""
    return TestClient(app, raise_server_exceptions=False)

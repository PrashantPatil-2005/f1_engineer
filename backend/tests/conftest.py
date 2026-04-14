"""Shared pytest fixtures for the F1 Engineer backend tests.

Tests run with the backend/ directory on sys.path (set in pyproject.toml),
so `from app.server import create_app` and `from config import config` resolve
the same way they do at runtime.
"""

import os
import sys
from pathlib import Path

import pytest

# Belt and braces: ensure backend/ is importable even when pytest is invoked
# from the repo root. pyproject's pythonpath handles the normal case.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Ensure the GROQ key is set *before* config.py is imported, so config.validate()
# doesn't trip during create_app(). The value is fake — tests never call the LLM.
os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")
os.environ.setdefault("FLASK_DEBUG", "false")


@pytest.fixture
def app():
    """Build a fresh Flask app for each test."""
    from app.server import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def reset_rate_limiter():
    """Clear the in-process rate-limit buckets between tests that touch /ask."""
    from app import routes

    routes._rate_limits.clear()
    yield
    routes._rate_limits.clear()

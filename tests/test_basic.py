"""
Basic smoke tests — ensure the app module imports cleanly
and core configuration is sane without requiring live services.
"""

import importlib
import os
import pytest


def test_settings_defaults():
    """Settings load with sensible defaults."""
    os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
    from app.config import get_settings

    settings = get_settings()
    assert settings.app_name == "Multi-Agent Research Assistant"
    assert settings.port == 8000
    assert settings.mongodb_url.startswith("mongodb")


def test_app_imports():
    """FastAPI app can be imported without raising."""
    try:
        import app.main  # noqa: F401
    except Exception as exc:
        pytest.fail(f"app.main import raised: {exc}")


def test_models_importable():
    """Pydantic models import without error."""
    from app.models import models as m  # noqa: F401
    assert hasattr(m, "ResearchStartRequest")

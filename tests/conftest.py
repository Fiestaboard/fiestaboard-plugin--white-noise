"""Plugin test fixtures and configuration."""

import pytest
from unittest.mock import patch, MagicMock

from src.plugins.testing import PluginTestCase, create_mock_response


@pytest.fixture(autouse=True)
def reset_plugin_singletons():
    """Reset plugin singletons before each test."""
    yield


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "intensity": "light",
        "drop_color": "white",
        "enabled": True,
    }


@pytest.fixture
def sample_manifest():
    """Sample manifest for plugin initialization."""
    return {
        "id": "white_noise",
        "name": "White Noise",
        "version": "1.0.0",
        "description": "Gentle rain / white noise mode",
        "author": "FiestaBoard Team",
        "settings_schema": {},
        "variables": {
            "groups": {
                "display": {"label": "Display"},
                "config": {"label": "Configuration"},
            },
            "simple": {
                "white_noise": {"description": "Full white noise rain pattern", "type": "string", "max_length": 200, "group": "display"},
                "intensity": {"description": "Current rain intensity level", "type": "string", "max_length": 6, "group": "config"},
                "drop_color": {"description": "Current raindrop color", "type": "string", "max_length": 6, "group": "config"},
                "active_drops": {"description": "Number of active raindrops", "type": "number", "max_length": 3, "group": "display"},
            },
        },
    }

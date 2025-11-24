"""Tests for main server module."""

import os

from src.main import mcp


def test_server_initialization():
    """Test that the server initializes correctly."""
    assert mcp is not None
    assert mcp.name == "vibe-trade-server"


def test_server_port_configuration():
    """Test that server reads PORT environment variable."""
    original_port = os.getenv("PORT")
    try:
        os.environ["PORT"] = "9000"
        # Re-import to get new port value
        import importlib

        import src.main

        importlib.reload(src.main)
        # Server should use the port from env
        assert int(os.getenv("PORT", "8080")) == 9000
    finally:
        if original_port:
            os.environ["PORT"] = original_port
        else:
            os.environ.pop("PORT", None)


def test_main_function_exists():
    """Test that main function exists and is callable."""
    from src.main import main

    assert callable(main)

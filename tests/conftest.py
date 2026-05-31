"""Pytest configuration and fixtures for CLI tests.

AIDEV-NOTE: This file ensures tests are isolated from system config files.
The STATSHED_URL environment variable is set to localhost:7828 for all tests
so that mock responses match the actual requests made.
"""

import pytest


@pytest.fixture(autouse=True)
def isolate_from_system_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests use default localhost URL regardless of system config.

    AIDEV-NOTE: The CLI can pick up config from /etc/statshed/statshed.yaml or
    ~/.config/statshed/statshed.yaml. This fixture ensures tests always use
    the localhost URL that the mock responses expect.
    """
    monkeypatch.setenv("STATSHED_URL", "http://localhost:7828")

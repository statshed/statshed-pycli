"""Integration tests for StatDash CLI against the real backend.

AIDEV-NOTE: These tests require the backend to be available. They test the CLI
against a real Flask test server to verify end-to-end functionality. The tests
are skipped if the backend is not available.
"""

import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import responses
from click.testing import CliRunner

# Add backend to path for integration tests
BACKEND_PATH = Path(__file__).parent.parent.parent.parent / "backend"
if BACKEND_PATH.exists():
    sys.path.insert(0, str(BACKEND_PATH))

from statdash_cli.errors import ExitCode  # noqa: E402
from statdash_cli.main import cli  # noqa: E402


def _find_free_port() -> int:
    """Find a free port to run the test server on."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# AIDEV-NOTE: Skip integration tests if backend is not available
try:
    from app import create_app
    from config import TestConfig
    from extensions import db

    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False


@pytest.fixture
def integration_server():
    """Start a Flask test server for integration testing.

    Returns:
        Tuple of (server_url, flask_app)
    """
    if not BACKEND_AVAILABLE:
        pytest.skip("Backend not available for integration tests")

    # Find a free port
    port = _find_free_port()

    # Clean up any leftover test database
    test_db_path = BACKEND_PATH / "test_statdash.db"
    if test_db_path.exists():
        os.remove(test_db_path)

    # Create test app
    config = TestConfig()
    app = create_app(config)

    # Create tables
    with app.app_context():
        db.create_all()

    # Start server in a thread
    # AIDEV-NOTE: Use werkzeug's run_simple for a lightweight test server
    # instead of the full socketio server which requires eventlet
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", port, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    # Wait for server to start
    time.sleep(0.1)

    yield f"http://127.0.0.1:{port}", app

    # Cleanup
    server.shutdown()
    with app.app_context():
        db.drop_all()
    if test_db_path.exists():
        os.remove(test_db_path)


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason="Backend not available")
class TestHealthIntegration:
    """Integration tests for the health command."""

    def test_health_empty(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test health command with no jobs."""
        url, _ = integration_server
        result = runner.invoke(cli, ["-u", url, "health"])
        assert result.exit_code == 0
        assert "EMPTY" in result.output

    def test_health_healthy(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test health command after submitting a success status."""
        url, _ = integration_server

        # Submit a success status first
        result = runner.invoke(
            cli, ["-u", url, "submit", "-g", "test", "-j", "job1", "-s", "success"]
        )
        assert result.exit_code == 0

        # Check health
        result = runner.invoke(cli, ["-u", url, "health"])
        assert result.exit_code == 0
        assert "HEALTHY" in result.output


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason="Backend not available")
class TestSubmitIntegration:
    """Integration tests for the submit command."""

    def test_submit_success(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test successful status submission."""
        url, _ = integration_server
        result = runner.invoke(
            cli,
            [
                "-u",
                url,
                "submit",
                "-g",
                "mygroup",
                "-j",
                "myjob",
                "-s",
                "success",
                "-m",
                "Test passed",
            ],
        )
        assert result.exit_code == 0
        assert "mygroup/myjob" in result.output

    def test_submit_creates_group(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test that submitting creates the group automatically."""
        url, _ = integration_server

        # Submit to a new group
        result = runner.invoke(
            cli, ["-u", url, "submit", "-g", "newgroup", "-j", "newjob", "-s", "progress"]
        )
        assert result.exit_code == 0

        # Verify group exists
        result = runner.invoke(cli, ["-u", url, "groups"])
        assert result.exit_code == 0
        assert "newgroup" in result.output


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason="Backend not available")
class TestGroupsIntegration:
    """Integration tests for the groups command."""

    def test_groups_empty(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test groups command with no groups."""
        url, _ = integration_server
        result = runner.invoke(cli, ["-u", url, "groups"])
        assert result.exit_code == 0
        assert "No groups found" in result.output

    def test_groups_list(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test listing groups."""
        url, _ = integration_server

        # Create some groups
        runner.invoke(cli, ["-u", url, "submit", "-g", "group-a", "-j", "job1", "-s", "success"])
        runner.invoke(cli, ["-u", url, "submit", "-g", "group-b", "-j", "job2", "-s", "error"])

        result = runner.invoke(cli, ["-u", url, "groups"])
        assert result.exit_code == 0
        assert "group-a" in result.output
        assert "group-b" in result.output


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason="Backend not available")
class TestJobsIntegration:
    """Integration tests for the jobs command."""

    def test_jobs_list(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test listing jobs in a group."""
        url, _ = integration_server

        # Create jobs in a group
        runner.invoke(cli, ["-u", url, "submit", "-g", "mygroup", "-j", "job1", "-s", "success"])
        runner.invoke(cli, ["-u", url, "submit", "-g", "mygroup", "-j", "job2", "-s", "error"])

        result = runner.invoke(cli, ["-u", url, "jobs", "mygroup"])
        assert result.exit_code == 0
        assert "job1" in result.output
        assert "job2" in result.output

    def test_jobs_not_found(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test jobs command with nonexistent group."""
        url, _ = integration_server
        result = runner.invoke(cli, ["-u", url, "jobs", "nonexistent"])
        assert result.exit_code == ExitCode.ERROR_NOT_FOUND


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason="Backend not available")
class TestConfigIntegration:
    """Integration tests for config commands."""

    def test_config_view(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test viewing global config."""
        url, _ = integration_server
        result = runner.invoke(cli, ["-u", url, "config"])
        assert result.exit_code == 0
        assert "Progress Timeout:" in result.output
        assert "Staleness Timeout:" in result.output

    def test_config_update(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test updating global config."""
        url, _ = integration_server
        result = runner.invoke(cli, ["-u", url, "config", "-p", "10"])
        assert result.exit_code == 0
        assert "10 minutes" in result.output


@pytest.mark.skipif(not BACKEND_AVAILABLE, reason="Backend not available")
class TestGroupConfigIntegration:
    """Integration tests for group-config command."""

    def test_group_config_view(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test viewing group config."""
        url, _ = integration_server

        # Create the group first
        runner.invoke(cli, ["-u", url, "submit", "-g", "mygroup", "-j", "job1", "-s", "success"])

        result = runner.invoke(cli, ["-u", url, "group-config", "mygroup"])
        assert result.exit_code == 0

    def test_group_config_not_found(self, runner: CliRunner, integration_server: tuple) -> None:
        """Test group-config with nonexistent group."""
        url, _ = integration_server
        result = runner.invoke(cli, ["-u", url, "group-config", "nonexistent"])
        assert result.exit_code == ExitCode.ERROR_NOT_FOUND


class TestErrorScenarios:
    """Test error scenarios without backend."""

    def test_connection_refused(self, runner: CliRunner) -> None:
        """Test connection refused error (real socket error).

        AIDEV-NOTE: No @responses.activate here - we want to hit a real
        non-existent port to test actual connection error handling.
        """
        result = runner.invoke(cli, ["-u", "http://localhost:59999", "health"])
        assert result.exit_code == ExitCode.ERROR_CONNECTION
        assert "Error:" in result.output

    @responses.activate
    def test_timeout_error(self, runner: CliRunner) -> None:
        """Test timeout error."""
        import requests

        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            body=requests.exceptions.Timeout("Request timed out"),
        )

        result = runner.invoke(cli, ["-u", "http://localhost:5000", "health"])
        assert result.exit_code == ExitCode.ERROR_TIMEOUT

    @responses.activate
    def test_404_not_found(self, runner: CliRunner) -> None:
        """Test 404 not found error."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups/nonexistent/jobs",
            json={"error": "Group 'nonexistent' not found"},
            status=404,
        )

        result = runner.invoke(cli, ["-u", "http://localhost:5000", "jobs", "nonexistent"])
        assert result.exit_code == ExitCode.ERROR_NOT_FOUND

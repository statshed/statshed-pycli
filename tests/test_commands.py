"""Tests for CLI commands."""

import json

import pytest
import requests
import responses
from click.testing import CliRunner

from statdash_cli.errors import ExitCode
from statdash_cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


class TestHealthCommand:
    """Test the health command."""

    @responses.activate
    def test_health_healthy(self, runner: CliRunner) -> None:
        """Test health command with healthy status."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={
                "status": "healthy",
                "total_jobs": 5,
                "by_status": {"success": 5, "error": 0, "progress": 0},
            },
            status=200,
        )

        result = runner.invoke(cli, ["health"])
        assert result.exit_code == 0
        assert "HEALTHY" in result.output

    @responses.activate
    def test_health_unhealthy(self, runner: CliRunner) -> None:
        """Test health command with unhealthy status."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={"status": "unhealthy", "total_jobs": 3},
            status=200,
        )

        result = runner.invoke(cli, ["health"])
        assert result.exit_code == ExitCode.ERROR_UNHEALTHY
        assert "UNHEALTHY" in result.output

    @responses.activate
    def test_health_json_output(self, runner: CliRunner) -> None:
        """Test health command with JSON output."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={"status": "healthy", "total_jobs": 5},
            status=200,
        )

        result = runner.invoke(cli, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "healthy"

    @responses.activate
    def test_health_connection_error(self, runner: CliRunner) -> None:
        """Test health command with connection error."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        result = runner.invoke(cli, ["health"])
        assert result.exit_code == ExitCode.ERROR_CONNECTION
        assert "Error:" in result.output


class TestSubmitCommand:
    """Test the submit command."""

    @responses.activate
    def test_submit_success(self, runner: CliRunner) -> None:
        """Test successful status submission."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            json={
                "success": True,
                "job": {
                    "group_name": "test-group",
                    "name": "test-job",
                    "status": "success",
                },
            },
            status=201,
        )

        result = runner.invoke(
            cli, ["submit", "-g", "test-group", "-j", "test-job", "-s", "success"]
        )
        assert result.exit_code == 0
        assert "test-group/test-job" in result.output

    @responses.activate
    def test_submit_with_message(self, runner: CliRunner) -> None:
        """Test submission with message."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            json={
                "success": True,
                "job": {"status": "error", "message": "Build failed"},
            },
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "submit",
                "-g",
                "builds",
                "-j",
                "build-123",
                "-s",
                "error",
                "-m",
                "Build failed",
            ],
        )
        assert result.exit_code == 0

    @responses.activate
    def test_submit_lenient_mode(self, runner: CliRunner) -> None:
        """Test that lenient mode (default) exits 0 on error."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        result = runner.invoke(cli, ["submit", "-g", "test", "-j", "test", "-s", "success"])
        # Lenient mode should exit 0 even on error
        assert result.exit_code == 0
        assert "Warning:" in result.output

    @responses.activate
    def test_submit_strict_mode(self, runner: CliRunner) -> None:
        """Test that strict mode exits with error code."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        result = runner.invoke(
            cli, ["submit", "-g", "test", "-j", "test", "-s", "success", "--strict"]
        )
        assert result.exit_code == ExitCode.ERROR_CONNECTION

    @responses.activate
    def test_submit_quiet_mode(self, runner: CliRunner) -> None:
        """Test that quiet mode suppresses output."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            json={"success": True, "job": {"status": "success"}},
            status=201,
        )

        result = runner.invoke(cli, ["-q", "submit", "-g", "test", "-j", "test", "-s", "success"])
        assert result.exit_code == 0
        assert result.output == ""

    def test_submit_invalid_status(self, runner: CliRunner) -> None:
        """Test that invalid status values are rejected."""
        result = runner.invoke(cli, ["submit", "-g", "test", "-j", "test", "-s", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


class TestGroupsCommand:
    """Test the groups command."""

    @responses.activate
    def test_groups_list(self, runner: CliRunner) -> None:
        """Test listing groups."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups",
            json={
                "groups": [
                    {"name": "group-a", "job_count": 3, "health": "healthy"},
                    {"name": "group-b", "job_count": 2, "health": "unhealthy"},
                ]
            },
            status=200,
        )

        result = runner.invoke(cli, ["groups"])
        assert result.exit_code == 0
        assert "group-a" in result.output
        assert "group-b" in result.output

    @responses.activate
    def test_groups_json(self, runner: CliRunner) -> None:
        """Test groups with JSON output."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups",
            json={"groups": [{"name": "test"}]},
            status=200,
        )

        result = runner.invoke(cli, ["groups", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "groups" in data


class TestJobsCommand:
    """Test the jobs command."""

    @responses.activate
    def test_jobs_list(self, runner: CliRunner) -> None:
        """Test listing jobs in a group."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups/test-group/jobs",
            json={
                "group": {"name": "test-group"},
                "jobs": [
                    {"name": "job-1", "status": "success"},
                    {"name": "job-2", "status": "error"},
                ],
            },
            status=200,
        )

        result = runner.invoke(cli, ["jobs", "test-group"])
        assert result.exit_code == 0
        assert "job-1" in result.output
        assert "job-2" in result.output

    @responses.activate
    def test_jobs_group_not_found(self, runner: CliRunner) -> None:
        """Test jobs command with nonexistent group."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups/nonexistent/jobs",
            json={"error": "Group not found"},
            status=404,
        )

        result = runner.invoke(cli, ["jobs", "nonexistent"])
        assert result.exit_code == ExitCode.ERROR_NOT_FOUND
        assert "not found" in result.output


class TestConfigCommand:
    """Test the config command."""

    @responses.activate
    def test_config_view(self, runner: CliRunner) -> None:
        """Test viewing global config."""
        responses.add(
            responses.GET,
            "http://localhost:5000/config",
            json={
                "progress_timeout_minutes": 5,
                "staleness_timeout_hours": 24,
            },
            status=200,
        )

        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0
        assert "5 minutes" in result.output
        assert "24 hours" in result.output

    @responses.activate
    def test_config_update(self, runner: CliRunner) -> None:
        """Test updating global config."""
        responses.add(
            responses.PUT,
            "http://localhost:5000/config",
            json={
                "progress_timeout_minutes": 10,
                "staleness_timeout_hours": 48,
            },
            status=200,
        )

        result = runner.invoke(cli, ["config", "-p", "10", "-s", "48"])
        assert result.exit_code == 0
        assert "10 minutes" in result.output


class TestGroupConfigCommand:
    """Test the group-config command."""

    @responses.activate
    def test_group_config_view(self, runner: CliRunner) -> None:
        """Test viewing group config."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups/test-group/config",
            json={
                "group": "test-group",
                "progress_timeout_minutes": None,
                "staleness_timeout_hours": 48,
                "effective_progress_timeout_minutes": 5,
                "effective_staleness_timeout_hours": 48,
            },
            status=200,
        )

        result = runner.invoke(cli, ["group-config", "test-group"])
        assert result.exit_code == 0
        assert "test-group" in result.output

    @responses.activate
    def test_group_config_update(self, runner: CliRunner) -> None:
        """Test updating group config."""
        responses.add(
            responses.PUT,
            "http://localhost:5000/groups/test-group/config",
            json={
                "group": "test-group",
                "progress_timeout_minutes": 15,
            },
            status=200,
        )

        result = runner.invoke(cli, ["group-config", "test-group", "-p", "15"])
        assert result.exit_code == 0

    @responses.activate
    def test_group_config_not_found(self, runner: CliRunner) -> None:
        """Test group-config with nonexistent group."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups/nonexistent/config",
            json={"error": "Group not found"},
            status=404,
        )

        result = runner.invoke(cli, ["group-config", "nonexistent"])
        assert result.exit_code == ExitCode.ERROR_NOT_FOUND


class TestCompletionCommand:
    """Test the completion command."""

    def test_completion_bash(self, runner: CliRunner) -> None:
        """Test bash completion script generation."""
        result = runner.invoke(cli, ["completion", "bash"])
        assert result.exit_code == 0
        assert "COMPREPLY" in result.output

    def test_completion_zsh(self, runner: CliRunner) -> None:
        """Test zsh completion script generation."""
        result = runner.invoke(cli, ["completion", "zsh"])
        assert result.exit_code == 0
        assert "compdef" in result.output

    def test_completion_fish(self, runner: CliRunner) -> None:
        """Test fish completion script generation."""
        result = runner.invoke(cli, ["completion", "fish"])
        assert result.exit_code == 0
        assert "complete -c statdash-cli" in result.output

    def test_completion_invalid_shell(self, runner: CliRunner) -> None:
        """Test that invalid shell name is rejected."""
        result = runner.invoke(cli, ["completion", "powershell"])
        assert result.exit_code != 0


class TestGlobalOptions:
    """Test global CLI options."""

    @responses.activate
    def test_custom_url(self, runner: CliRunner) -> None:
        """Test using custom URL."""
        responses.add(
            responses.GET,
            "http://custom.example.com:8080/health",
            json={"status": "healthy"},
            status=200,
        )

        result = runner.invoke(cli, ["-u", "http://custom.example.com:8080", "health"])
        assert result.exit_code == 0

    @responses.activate
    def test_global_json_option(self, runner: CliRunner) -> None:
        """Test --json global option."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={"status": "healthy"},
            status=200,
        )

        result = runner.invoke(cli, ["--json", "health"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "status" in data

    def test_version(self, runner: CliRunner) -> None:
        """Test --version option."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output or "version" in result.output.lower()

    def test_help(self, runner: CliRunner) -> None:
        """Test --help option."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "StatDash CLI" in result.output
        assert "health" in result.output
        assert "submit" in result.output

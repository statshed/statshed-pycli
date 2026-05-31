"""Tests for output formatting."""

import json

import pytest

from statshed_cli.output import (
    RICH_AVAILABLE,
    JsonFormatter,
    PlainFormatter,
    RichFormatter,
    get_formatter,
    should_use_color,
)


class TestPlainFormatter:
    """Test plain text output formatting."""

    def test_health_output(self) -> None:
        """Test health output formatting."""
        formatter = PlainFormatter()
        data = {
            "status": "healthy",
            "total_jobs": 10,
            "by_status": {
                "success": 8,
                "error": 1,
                "progress": 1,
                "timeout": 0,
                "stale": 0,
            },
        }
        output = formatter.health(data)

        assert "HEALTHY" in output
        assert "Total Jobs: 10" in output
        assert "Success: 8" in output
        assert "Error: 1" in output

    def test_health_output_unhealthy(self) -> None:
        """Test health output for unhealthy status."""
        formatter = PlainFormatter()
        data = {"status": "unhealthy", "total_jobs": 5}
        output = formatter.health(data)

        assert "UNHEALTHY" in output
        assert "❌" in output

    def test_groups_output(self) -> None:
        """Test groups list output formatting."""
        formatter = PlainFormatter()
        data = {
            "groups": [
                {
                    "name": "nightly-builds",
                    "job_count": 5,
                    "health": "healthy",
                    "status_counts": {"success": 5, "error": 0},
                },
                {
                    "name": "deployments",
                    "job_count": 3,
                    "health": "unhealthy",
                    "status_counts": {"success": 2, "error": 1},
                },
            ]
        }
        output = formatter.groups(data)

        assert "nightly-builds" in output
        assert "5 jobs" in output
        assert "deployments" in output
        assert "error: 1" in output

    def test_groups_empty(self) -> None:
        """Test groups output when no groups exist."""
        formatter = PlainFormatter()
        output = formatter.groups({"groups": []})
        assert "No groups found" in output

    def test_jobs_output(self) -> None:
        """Test jobs list output formatting."""
        formatter = PlainFormatter()
        data = {
            "group": {"name": "nightly-builds"},
            "jobs": [
                {"name": "backend-tests", "status": "success", "message": "All passed"},
                {"name": "frontend-tests", "status": "error", "message": "3 failures"},
            ],
        }
        output = formatter.jobs(data)

        assert "Group: nightly-builds" in output
        assert "backend-tests" in output
        assert "All passed" in output
        assert "error" in output

    def test_jobs_empty(self) -> None:
        """Test jobs output when no jobs exist."""
        formatter = PlainFormatter()
        output = formatter.jobs({"group": {"name": "empty-group"}, "jobs": []})
        assert "No jobs found" in output

    def test_config_output(self) -> None:
        """Test config output formatting."""
        formatter = PlainFormatter()
        data = {
            "progress_timeout_minutes": 5,
            "staleness_timeout_hours": 24,
        }
        output = formatter.config(data)

        assert "Progress Timeout: 5 minutes" in output
        assert "Staleness Timeout: 24 hours" in output

    def test_group_config_output(self) -> None:
        """Test group config output formatting."""
        formatter = PlainFormatter()
        data = {
            "group": "nightly-builds",
            "progress_timeout_minutes": None,
            "staleness_timeout_hours": 48,
            "effective_progress_timeout_minutes": 5,
            "effective_staleness_timeout_hours": 48,
        }
        output = formatter.group_config(data)

        assert "Group: nightly-builds" in output
        assert "5 minutes (global default)" in output
        assert "48 hours (override)" in output

    def test_submit_success(self) -> None:
        """Test submit success output."""
        formatter = PlainFormatter()
        data = {
            "job": {
                "group_name": "test-group",
                "name": "test-job",
                "status": "success",
            }
        }
        output = formatter.submit_success(data)

        assert "test-group/test-job" in output
        assert "success" in output

    def test_error_output(self) -> None:
        """Test error message formatting."""
        formatter = PlainFormatter()
        output = formatter.error("Something went wrong")
        assert "Error: Something went wrong" in output


class TestJsonFormatter:
    """Test JSON output formatting."""

    def test_health_output(self) -> None:
        """Test health JSON output."""
        formatter = JsonFormatter()
        data = {"status": "healthy", "total_jobs": 5}
        output = formatter.health(data)

        parsed = json.loads(output)
        assert parsed["status"] == "healthy"
        assert parsed["total_jobs"] == 5

    def test_groups_output(self) -> None:
        """Test groups JSON output."""
        formatter = JsonFormatter()
        data = {"groups": [{"name": "test", "job_count": 3}]}
        output = formatter.groups(data)

        parsed = json.loads(output)
        assert len(parsed["groups"]) == 1

    def test_error_output(self) -> None:
        """Test error JSON output."""
        formatter = JsonFormatter()
        output = formatter.error("Something went wrong")

        parsed = json.loads(output)
        assert parsed["error"] == "Something went wrong"

    def test_all_methods_return_valid_json(self) -> None:
        """Test that all methods return valid JSON."""
        formatter = JsonFormatter()

        # Each method should return valid JSON
        json.loads(formatter.health({"status": "healthy"}))
        json.loads(formatter.groups({"groups": []}))
        json.loads(formatter.jobs({"group": {}, "jobs": []}))
        json.loads(formatter.config({}))
        json.loads(formatter.group_config({}))
        json.loads(formatter.submit_success({}))
        json.loads(formatter.error("test"))


class TestGetFormatter:
    """Test formatter selection."""

    def test_json_format(self) -> None:
        """Test JSON formatter selection."""
        formatter = get_formatter(output_format="json")
        assert isinstance(formatter, JsonFormatter)

    def test_table_format(self) -> None:
        """Test table/plain formatter selection."""
        formatter = get_formatter(output_format="table")
        assert isinstance(formatter, PlainFormatter)

    def test_default_format(self) -> None:
        """Test default formatter."""
        formatter = get_formatter()
        assert isinstance(formatter, PlainFormatter)


class TestShouldUseColor:
    """Test color detection."""

    def test_never(self) -> None:
        """Test color: never."""
        assert should_use_color("never") is False

    def test_always(self) -> None:
        """Test color: always."""
        assert should_use_color("always") is True

    def test_auto_default(self) -> None:
        """Test color: auto (depends on TTY)."""
        # In test environment, stdout is usually not a TTY
        result = should_use_color("auto")
        assert isinstance(result, bool)


@pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich library not installed")
class TestRichFormatter:
    """Test Rich terminal output formatting.

    These tests are skipped if Rich is not installed.
    """

    def test_health_output(self) -> None:
        """Test health output with Rich formatting."""
        formatter = RichFormatter()
        data = {
            "status": "healthy",
            "total_jobs": 10,
            "by_status": {
                "success": 8,
                "error": 1,
                "progress": 1,
                "timeout": 0,
                "stale": 0,
            },
        }
        output = formatter.health(data)

        # Rich output contains ANSI escape codes for styling
        assert "HEALTHY" in output
        assert "Total Jobs" in output
        assert "10" in output

    def test_health_output_unhealthy(self) -> None:
        """Test health output for unhealthy status with Rich formatting."""
        formatter = RichFormatter()
        data = {"status": "unhealthy", "total_jobs": 5}
        output = formatter.health(data)

        assert "UNHEALTHY" in output

    def test_groups_output(self) -> None:
        """Test groups list output with Rich formatting."""
        formatter = RichFormatter()
        data = {
            "groups": [
                {
                    "name": "nightly-builds",
                    "job_count": 5,
                    "health": "healthy",
                    "status_counts": {"success": 5, "error": 0},
                },
                {
                    "name": "deployments",
                    "job_count": 3,
                    "health": "unhealthy",
                    "status_counts": {"success": 2, "error": 1},
                },
            ]
        }
        output = formatter.groups(data)

        assert "nightly-builds" in output
        assert "deployments" in output
        assert "Groups" in output  # Table title

    def test_groups_empty(self) -> None:
        """Test groups output when no groups exist with Rich formatting."""
        formatter = RichFormatter()
        output = formatter.groups({"groups": []})
        assert "No groups found" in output

    def test_jobs_output(self) -> None:
        """Test jobs list output with Rich formatting."""
        formatter = RichFormatter()
        data = {
            "group": {"name": "nightly-builds"},
            "jobs": [
                {"name": "backend-tests", "status": "success", "message": "All passed"},
                {"name": "frontend-tests", "status": "error", "message": "3 failures"},
            ],
        }
        output = formatter.jobs(data)

        assert "nightly-builds" in output
        assert "backend-tests" in output
        assert "frontend-tests" in output

    def test_jobs_empty(self) -> None:
        """Test jobs output when no jobs exist with Rich formatting."""
        formatter = RichFormatter()
        output = formatter.jobs({"group": {"name": "empty-group"}, "jobs": []})
        assert "No jobs found" in output

    def test_config_output(self) -> None:
        """Test config output with Rich formatting."""
        formatter = RichFormatter()
        data = {
            "progress_timeout_minutes": 5,
            "staleness_timeout_hours": 24,
        }
        output = formatter.config(data)

        assert "Progress Timeout" in output
        assert "5 minutes" in output
        assert "Staleness Timeout" in output
        assert "24 hours" in output

    def test_group_config_output(self) -> None:
        """Test group config output with Rich formatting."""
        formatter = RichFormatter()
        data = {
            "group": "nightly-builds",
            "progress_timeout_minutes": None,
            "staleness_timeout_hours": 48,
            "effective_progress_timeout_minutes": 5,
            "effective_staleness_timeout_hours": 48,
        }
        output = formatter.group_config(data)

        assert "nightly-builds" in output
        assert "Progress Timeout" in output
        assert "Staleness Timeout" in output

    def test_submit_success(self) -> None:
        """Test submit success output with Rich formatting."""
        formatter = RichFormatter()
        data = {
            "job": {
                "group_name": "test-group",
                "name": "test-job",
                "status": "success",
            }
        }
        output = formatter.submit_success(data)

        assert "test-group" in output
        assert "test-job" in output
        assert "success" in output

    def test_error_output(self) -> None:
        """Test error message with Rich formatting."""
        formatter = RichFormatter()
        output = formatter.error("Something went wrong")
        assert "Something went wrong" in output
        assert "Error" in output  # Panel title

    def test_all_status_colors(self) -> None:
        """Test that all status types produce valid output."""
        formatter = RichFormatter()

        for status in ["success", "error", "progress", "timeout", "stale"]:
            data = {"status": status, "total_jobs": 1, "by_status": {status: 1}}
            output = formatter.health(data)
            assert status.upper() in output


class TestGetFormatterWithRich:
    """Test formatter selection with Rich availability."""

    @pytest.mark.skipif(not RICH_AVAILABLE, reason="Rich library not installed")
    def test_table_format_with_color_always(self) -> None:
        """Test that RichFormatter is selected when color is 'always' and Rich is available."""
        formatter = get_formatter(output_format="table", color="always")
        assert isinstance(formatter, RichFormatter)

    def test_table_format_with_color_never(self) -> None:
        """Test that PlainFormatter is selected when color is 'never'."""
        formatter = get_formatter(output_format="table", color="never")
        assert isinstance(formatter, PlainFormatter)

    def test_json_format_ignores_color(self) -> None:
        """Test that JsonFormatter is always used for JSON output."""
        formatter = get_formatter(output_format="json", color="always")
        assert isinstance(formatter, JsonFormatter)

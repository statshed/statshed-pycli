"""Tests for CLI commands."""

import json
from pathlib import Path
from unittest import mock

import pytest
import requests
import responses
from click.testing import CliRunner

from reportingin_cli.errors import ExitCode
from reportingin_cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner.

    AIDEV-NOTE: Click 8.x CliRunner captures both stdout and stderr in result.output
    by default (there's no mix_stderr parameter - it was added in Click 9.x).
    Warnings printed to stderr via click.echo(err=True) are included in result.output.
    """
    return CliRunner()


class TestHealthCommand:
    """Test the health command."""

    @responses.activate
    def test_health_healthy(self, runner: CliRunner) -> None:
        """Test health command with healthy status."""
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
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
            "http://localhost:7828/health",
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
            "http://localhost:7828/health",
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
            "http://localhost:7828/health",
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
            "http://localhost:7828/status",
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
            "http://localhost:7828/status",
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
            "http://localhost:7828/status",
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
            "http://localhost:7828/status",
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
            "http://localhost:7828/status",
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

    @responses.activate
    def test_submit_syslog_on_error(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that syslog is used when configured and error occurs."""
        # Create config file with syslog enabled
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
url: http://localhost:7828
submit:
  syslog: true
  syslog_facility: local0
""")
        monkeypatch.setenv("REPORTINGIN_CONFIG", str(config_file))

        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        with mock.patch("reportingin_cli.logging.log_to_syslog") as mock_syslog:
            result = runner.invoke(cli, ["submit", "-g", "test", "-j", "test", "-s", "success"])
            # Lenient mode should exit 0
            assert result.exit_code == 0
            # Syslog should have been called
            mock_syslog.assert_called_once()
            # No warning on stderr when syslog is enabled
            assert "Warning:" not in result.output

    @responses.activate
    def test_submit_with_log_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test successful submission with log file."""
        # Create a test log file
        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={
                "success": True,
                "job": {
                    "group_name": "test-group",
                    "name": "test-job",
                    "status": "success",
                    "has_log": True,
                    "log_line_count": 3,
                    "log_truncated": False,
                },
            },
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "submit",
                "-g",
                "test-group",
                "-j",
                "test-job",
                "-s",
                "success",
                "--log",
                str(log_file),
            ],
        )
        assert result.exit_code == 0
        assert "test-group/test-job" in result.output

    def test_submit_with_log_file_not_found(self, runner: CliRunner) -> None:
        """Test that nonexistent log file is rejected."""
        result = runner.invoke(
            cli,
            [
                "submit",
                "-g",
                "test",
                "-j",
                "test",
                "-s",
                "success",
                "--log",
                "/nonexistent/path/to/file.log",
            ],
        )
        assert result.exit_code != 0
        # Click should show error about file not existing
        assert "does not exist" in result.output.lower() or "not found" in result.output.lower()

    @responses.activate
    def test_submit_with_log_uploads_disabled_warning(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test that warning is shown when log uploads are disabled on server."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Test log content")

        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={
                "success": True,
                "job": {
                    "group_name": "test-group",
                    "name": "test-job",
                    "status": "success",
                    "has_log": False,
                },
                "warning": "Log uploads are disabled",
            },
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "submit",
                "-g",
                "test-group",
                "-j",
                "test-job",
                "-s",
                "success",
                "--log",
                str(log_file),
            ],
        )
        assert result.exit_code == 0
        assert "test-group/test-job" in result.output
        # Warning should be shown
        assert "Log uploads are disabled" in result.output

    @responses.activate
    def test_submit_with_log_and_message(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test submission with both log file and message."""
        log_file = tmp_path / "test.log"
        log_file.write_text("Build output here")

        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={
                "success": True,
                "job": {
                    "group_name": "builds",
                    "name": "build-123",
                    "status": "error",
                    "message": "Build failed",
                    "has_log": True,
                },
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
                "-l",
                str(log_file),
            ],
        )
        assert result.exit_code == 0


class TestStreamCommand:
    """Test the stream command.

    AIDEV-NOTE: These tests use ``--min-time 0`` so every eligible line is
    submitted immediately. Debounce/timing semantics are covered by the unit
    tests in ``test_stream.py``. Click's CliRunner provides stdin via an
    in-memory stream without a real fd, so ``_run_stream_loop`` hits the
    fallback line-iteration path.
    """

    @responses.activate
    def test_stream_submits_each_line(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            ["stream", "-g", "test-group", "-j", "test-job", "--min-time", "0"],
            input="line one\nline two\nline three\n",
        )

        assert result.exit_code == 0
        assert len(responses.calls) == 3
        bodies = [json.loads(call.request.body) for call in responses.calls]
        assert [b["message"] for b in bodies] == ["line one", "line two", "line three"]
        assert all(b["status"] == "progress" for b in bodies)
        assert all(b["group"] == "test-group" and b["job"] == "test-job" for b in bodies)

    @responses.activate
    def test_stream_echoes_by_default(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            ["stream", "-g", "g", "-j", "j", "--min-time", "0"],
            input="hello\nworld\n",
        )

        assert result.exit_code == 0
        assert "hello" in result.output
        assert "world" in result.output

    @responses.activate
    def test_stream_swallow_suppresses_echo(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            ["stream", "-g", "g", "-j", "j", "--min-time", "0", "--swallow"],
            input="secret\n",
        )

        assert result.exit_code == 0
        assert "secret" not in result.output
        assert len(responses.calls) == 1

    @responses.activate
    def test_stream_regex_filter(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "stream",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--regex",
                "ERROR",
                "--regex",
                "WARN",
            ],
            input="INFO start\nERROR boom\nDEBUG idle\nWARN slow\n",
        )

        assert result.exit_code == 0
        messages = [json.loads(call.request.body)["message"] for call in responses.calls]
        assert messages == ["ERROR boom", "WARN slow"]

    @responses.activate
    def test_stream_ignore_filter(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "stream",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--ignore",
                "heartbeat",
            ],
            input="work started\nheartbeat\nwork done\n",
        )

        assert result.exit_code == 0
        messages = [json.loads(call.request.body)["message"] for call in responses.calls]
        assert messages == ["work started", "work done"]

    @responses.activate
    def test_stream_ignore_case(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "stream",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--regex",
                "error",
                "--ignore-case",
            ],
            input="ERROR big\nError small\nnothing\n",
        )

        assert result.exit_code == 0
        messages = [json.loads(call.request.body)["message"] for call in responses.calls]
        assert messages == ["ERROR big", "Error small"]

    @responses.activate
    def test_stream_strips_ansi(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            ["stream", "-g", "g", "-j", "j", "--min-time", "0"],
            input="\x1b[32mdone\x1b[0m\n",
        )

        assert result.exit_code == 0
        messages = [json.loads(call.request.body)["message"] for call in responses.calls]
        assert messages == ["done"]

    @responses.activate
    def test_stream_lenient_mode_continues_on_error(self, runner: CliRunner) -> None:
        # AIDEV-NOTE: Can't use ``responses`` here because we want one call to
        # succeed and another to fail; sequencing with responses is awkward.
        # We just simulate outright connection failure and verify the stream
        # swallows it and exits 0.
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            body=requests.exceptions.ConnectionError("boom"),
        )

        result = runner.invoke(
            cli,
            ["stream", "-g", "g", "-j", "j", "--min-time", "0"],
            input="alpha\nbeta\n",
        )

        assert result.exit_code == 0
        assert "Warning:" in result.output

    @responses.activate
    def test_stream_strict_mode_exits_on_error(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            body=requests.exceptions.ConnectionError("boom"),
        )

        result = runner.invoke(
            cli,
            ["stream", "-g", "g", "-j", "j", "--min-time", "0", "--strict"],
            input="alpha\nbeta\n",
        )

        assert result.exit_code == ExitCode.ERROR_CONNECTION

    def test_stream_invalid_regex(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            ["stream", "-g", "g", "-j", "j", "--regex", "[unclosed"],
            input="",
        )

        assert result.exit_code == ExitCode.ERROR_INVALID_ARGS
        assert "Invalid regex" in result.output

    def test_stream_negative_min_time_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            ["stream", "-g", "g", "-j", "j", "--min-time", "-1"],
            input="",
        )

        assert result.exit_code != 0
        assert "Invalid value" in result.output


class TestWrapCommand:
    """Test the wrap command.

    AIDEV-NOTE: These are end-to-end tests exercising real subprocess execution
    via ``sh -c``. Because the child's stdout/stderr are genuine pipes, the
    selector loop in ``wrap.run_wrapped`` runs exactly as in production. We use
    ``--min-time 0`` so each line is submitted immediately (no debounce window
    to drive manually).
    """

    @responses.activate
    def test_wrap_submits_stdout_and_stderr(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--",
                "sh",
                "-c",
                "echo out-line; echo err-line >&2",
            ],
        )

        assert result.exit_code == 0
        bodies = [json.loads(call.request.body) for call in responses.calls]
        messages = {b["message"] for b in bodies}
        assert messages == {"out-line", "err-line"}
        assert all(b["status"] == "progress" for b in bodies)

    @responses.activate
    def test_wrap_echoes_stdout_and_stderr(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--",
                "sh",
                "-c",
                "echo hello; echo world >&2",
            ],
        )

        assert result.exit_code == 0
        # Click's CliRunner merges stdout+stderr into result.output.
        assert "hello" in result.output
        assert "world" in result.output

    @responses.activate
    def test_wrap_swallow_suppresses_echo(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--swallow",
                "--",
                "sh",
                "-c",
                "echo secret; echo alsosecret >&2",
            ],
        )

        assert result.exit_code == 0
        assert "secret" not in result.output
        assert "alsosecret" not in result.output
        assert len(responses.calls) == 2

    @responses.activate
    def test_wrap_propagates_exit_code(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            ["wrap", "-g", "g", "-j", "j", "--min-time", "0", "--", "sh", "-c", "exit 7"],
        )

        assert result.exit_code == 7

    @responses.activate
    def test_wrap_suppress_exitcode_masks_nonzero(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--suppress-exitcode",
                "--",
                "sh",
                "-c",
                "echo x; exit 9",
            ],
        )

        assert result.exit_code == 0

    @responses.activate
    def test_wrap_report_exit_submits_success(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "success"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--report-exit",
                "--",
                "sh",
                "-c",
                "echo final-line",
            ],
        )

        assert result.exit_code == 0
        bodies = [json.loads(call.request.body) for call in responses.calls]
        # Progress update first, then the final "success" with last line as message.
        assert bodies[-1] == {
            "group": "g",
            "job": "j",
            "status": "success",
            "message": "final-line",
        }

    @responses.activate
    def test_wrap_report_exit_submits_error_on_nonzero(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "error"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--report-exit",
                "--",
                "sh",
                "-c",
                "echo bad-output; exit 2",
            ],
        )

        assert result.exit_code == 2
        bodies = [json.loads(call.request.body) for call in responses.calls]
        assert bodies[-1] == {
            "group": "g",
            "job": "j",
            "status": "error",
            "message": "bad-output",
        }

    @responses.activate
    def test_wrap_report_exit_falls_back_when_no_output(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "error"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--report-exit",
                "--",
                "sh",
                "-c",
                "exit 4",
            ],
        )

        assert result.exit_code == 4
        bodies = [json.loads(call.request.body) for call in responses.calls]
        assert len(bodies) == 1
        assert bodies[0]["status"] == "error"
        assert bodies[0]["message"] == "exited with code 4"

    @responses.activate
    def test_wrap_regex_filter(self, runner: CliRunner) -> None:
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--regex",
                "ERROR",
                "--",
                "sh",
                "-c",
                "echo INFO line; echo ERROR boom",
            ],
        )

        assert result.exit_code == 0
        bodies = [json.loads(call.request.body) for call in responses.calls]
        assert len(bodies) == 1
        assert bodies[0]["message"] == "ERROR boom"

    def test_wrap_missing_command_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["wrap", "-g", "g", "-j", "j"])
        # Click reports a usage error (exit code 2) when the required COMMAND
        # argument is missing.
        assert result.exit_code != 0

    def test_wrap_command_not_found(self, runner: CliRunner) -> None:
        result = runner.invoke(
            cli,
            ["wrap", "-g", "g", "-j", "j", "--", "this-command-does-not-exist-abc123"],
        )
        assert result.exit_code == ExitCode.ERROR_INVALID_ARGS

    @responses.activate
    def test_wrap_attach_log_on_error(self, runner: CliRunner, tmp_path: Path) -> None:
        """On non-zero exit with --attach-log, a multipart upload should happen."""
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "error"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--attach-log",
                "--",
                "sh",
                "-c",
                "echo line-a; echo line-b >&2; exit 5",
            ],
        )

        assert result.exit_code == 5
        # 2 progress posts + 1 final error post = 3 calls.
        assert len(responses.calls) == 3
        final = responses.calls[-1].request
        # Multipart form requests use "multipart/form-data" content-type.
        content_type = final.headers.get("Content-Type", "")
        assert content_type.startswith("multipart/form-data")
        # Body should contain both the captured stdout and stderr lines.
        body = final.body
        body_text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
        assert "line-a" in body_text
        assert "line-b" in body_text

    @responses.activate
    def test_wrap_attach_log_skipped_on_success(self, runner: CliRunner) -> None:
        """On zero exit with --attach-log, no log should be attached."""
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "success"}},
            status=201,
        )

        result = runner.invoke(
            cli,
            [
                "wrap",
                "-g",
                "g",
                "-j",
                "j",
                "--min-time",
                "0",
                "--attach-log",
                "--",
                "sh",
                "-c",
                "echo ok",
            ],
        )

        assert result.exit_code == 0
        final = responses.calls[-1].request
        # No multipart: content-type should be JSON on the final call.
        assert final.headers.get("Content-Type", "").startswith("application/json")
        body = json.loads(final.body)
        assert body["status"] == "success"
        assert body["message"] == "ok"


class TestGroupsCommand:
    """Test the groups command."""

    @responses.activate
    def test_groups_list(self, runner: CliRunner) -> None:
        """Test listing groups."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups",
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
            "http://localhost:7828/groups",
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
            "http://localhost:7828/groups/test-group/jobs",
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
            "http://localhost:7828/groups/nonexistent/jobs",
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
            "http://localhost:7828/config",
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
            "http://localhost:7828/config",
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
            "http://localhost:7828/groups/test-group/config",
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
            "http://localhost:7828/groups/test-group/config",
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
            "http://localhost:7828/groups/nonexistent/config",
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
        assert "complete -c reportingin" in result.output

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
            "http://localhost:7828/health",
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
        assert "Reporting In CLI" in result.output
        assert "health" in result.output
        assert "submit" in result.output

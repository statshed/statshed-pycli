"""Tests for shell completion functionality."""

import os
from unittest.mock import MagicMock

import click
import pytest
import responses

from reportingin_cli.completion import (
    complete_group_names,
    complete_job_names,
    complete_status_values,
    get_completion_script,
)


class TestGetCompletionScript:
    """Test completion script generation."""

    def test_bash_completion(self) -> None:
        """Test Bash completion script generation."""
        script = get_completion_script("bash")
        assert "bash" in script.lower() or "_reportingin" in script
        assert "complete" in script

    def test_zsh_completion(self) -> None:
        """Test Zsh completion script generation."""
        script = get_completion_script("zsh")
        assert "#compdef" in script or "_reportingin" in script

    def test_fish_completion(self) -> None:
        """Test Fish completion script generation."""
        script = get_completion_script("fish")
        assert "function" in script or "complete" in script

    def test_unsupported_shell(self) -> None:
        """Test that unsupported shells raise an error."""
        with pytest.raises(click.BadParameter):
            get_completion_script("powershell")


class TestCompleteGroupNames:
    """Test dynamic group name completion."""

    @responses.activate
    def test_returns_group_names(self) -> None:
        """Test that group names are returned from API."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups",
            json={
                "groups": [
                    {"name": "nightly-builds", "health": "healthy", "job_count": 5},
                    {"name": "deployments", "health": "unhealthy", "job_count": 3},
                ]
            },
            status=200,
        )

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_group_names(ctx, param, "")
        names = [c.value for c in completions]

        assert "nightly-builds" in names
        assert "deployments" in names

    @responses.activate
    def test_filters_by_prefix(self) -> None:
        """Test that completions are filtered by prefix."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups",
            json={
                "groups": [
                    {"name": "nightly-builds", "health": "healthy", "job_count": 5},
                    {"name": "deployments", "health": "unhealthy", "job_count": 3},
                ]
            },
            status=200,
        )

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_group_names(ctx, param, "night")
        names = [c.value for c in completions]

        assert "nightly-builds" in names
        assert "deployments" not in names

    @responses.activate
    def test_returns_empty_on_api_error(self) -> None:
        """Test that empty list is returned on API error."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups",
            json={"error": "Server error"},
            status=500,
        )

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_group_names(ctx, param, "")
        assert completions == []

    @responses.activate
    def test_returns_empty_on_connection_error(self) -> None:
        """Test that empty list is returned on connection error."""
        import requests

        # Mock a connection error
        responses.add(
            responses.GET,
            "http://localhost:7828/groups",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_group_names(ctx, param, "")
        assert completions == []

    @responses.activate
    def test_uses_env_url(self) -> None:
        """Test that REPORTINGIN_URL environment variable is used."""
        responses.add(
            responses.GET,
            "http://custom.example.com/groups",
            json={"groups": [{"name": "test-group", "health": "healthy", "job_count": 1}]},
            status=200,
        )

        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        os.environ["REPORTINGIN_URL"] = "http://custom.example.com"
        try:
            completions = complete_group_names(ctx, param, "")
            names = [c.value for c in completions]
            assert "test-group" in names
        finally:
            os.environ.pop("REPORTINGIN_URL", None)


class TestCompleteJobNames:
    """Test dynamic job name completion."""

    @responses.activate
    def test_returns_job_names(self) -> None:
        """Test that job names are returned from API."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/test-group/jobs",
            json={
                "jobs": [
                    {"name": "backend-tests", "status": "success"},
                    {"name": "frontend-tests", "status": "error"},
                ]
            },
            status=200,
        )

        ctx = MagicMock(spec=click.Context)
        ctx.params = {"group": "test-group"}
        param = MagicMock(spec=click.Parameter)

        completions = complete_job_names(ctx, param, "")
        names = [c.value for c in completions]

        assert "backend-tests" in names
        assert "frontend-tests" in names

    @responses.activate
    def test_filters_by_prefix(self) -> None:
        """Test that job completions are filtered by prefix."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/test-group/jobs",
            json={
                "jobs": [
                    {"name": "backend-tests", "status": "success"},
                    {"name": "frontend-tests", "status": "error"},
                ]
            },
            status=200,
        )

        ctx = MagicMock(spec=click.Context)
        ctx.params = {"group": "test-group"}
        param = MagicMock(spec=click.Parameter)

        completions = complete_job_names(ctx, param, "back")
        names = [c.value for c in completions]

        assert "backend-tests" in names
        assert "frontend-tests" not in names

    def test_returns_empty_without_group(self) -> None:
        """Test that empty list is returned when no group is specified."""
        ctx = MagicMock(spec=click.Context)
        ctx.params = {}
        param = MagicMock(spec=click.Parameter)

        completions = complete_job_names(ctx, param, "")
        assert completions == []

    @responses.activate
    def test_url_encodes_group_name(self) -> None:
        """Test that group names with special characters are URL encoded."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/group%20with%20spaces/jobs",
            json={"jobs": [{"name": "test-job", "status": "success"}]},
            status=200,
        )

        ctx = MagicMock(spec=click.Context)
        ctx.params = {"group": "group with spaces"}
        param = MagicMock(spec=click.Parameter)

        completions = complete_job_names(ctx, param, "")
        names = [c.value for c in completions]

        assert "test-job" in names


class TestCompleteStatusValues:
    """Test status value completion."""

    def test_returns_all_statuses(self) -> None:
        """Test that all status values are returned."""
        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_status_values(ctx, param, "")
        values = [c.value for c in completions]

        assert "success" in values
        assert "error" in values
        assert "progress" in values

    def test_filters_by_prefix(self) -> None:
        """Test that status values are filtered by prefix."""
        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_status_values(ctx, param, "s")
        values = [c.value for c in completions]

        assert "success" in values
        assert "error" not in values
        assert "progress" not in values

    def test_includes_help_text(self) -> None:
        """Test that completion items include help text."""
        ctx = MagicMock(spec=click.Context)
        param = MagicMock(spec=click.Parameter)

        completions = complete_status_values(ctx, param, "")

        for completion in completions:
            assert completion.help is not None
            assert len(completion.help) > 0

"""Tests for the API client."""

import pytest
import requests
import responses

from statdash_cli.client import ApiClient
from statdash_cli.errors import ApiError, NotFoundError
from statdash_cli.errors import ConnectionError as StatDashConnectionError


class TestApiClientInit:
    """Test ApiClient initialization."""

    def test_init_default_timeout(self) -> None:
        """Test client initialization with default timeout."""
        client = ApiClient("http://localhost:5000")
        assert client.base_url == "http://localhost:5000"
        assert client.timeout == 10

    def test_init_custom_timeout(self) -> None:
        """Test client initialization with custom timeout."""
        client = ApiClient("http://localhost:5000", timeout=30)
        assert client.timeout == 30

    def test_init_strips_trailing_slash(self) -> None:
        """Test that trailing slashes are stripped from base URL."""
        client = ApiClient("http://localhost:5000/")
        assert client.base_url == "http://localhost:5000"

    def test_init_retry_defaults(self) -> None:
        """Test client initialization with default retry settings."""
        client = ApiClient("http://localhost:5000")
        assert client.retries == 0
        assert client.retry_delay == 1.0

    def test_init_custom_retries(self) -> None:
        """Test client initialization with custom retry settings."""
        client = ApiClient("http://localhost:5000", retries=3, retry_delay=0.5)
        assert client.retries == 3
        assert client.retry_delay == 0.5


class TestApiClientHealth:
    """Test health endpoint."""

    @responses.activate
    def test_get_health_healthy(self) -> None:
        """Test getting healthy status."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={
                "status": "healthy",
                "total_jobs": 5,
                "healthy": 5,
                "by_status": {"success": 5, "error": 0, "progress": 0},
            },
            status=200,
        )

        client = ApiClient("http://localhost:5000")
        result = client.get_health()

        assert result["status"] == "healthy"
        assert result["total_jobs"] == 5

    @responses.activate
    def test_get_health_connection_error(self) -> None:
        """Test connection error handling."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        client = ApiClient("http://localhost:5000")
        with pytest.raises(StatDashConnectionError, match="Could not connect"):
            client.get_health()


class TestApiClientSubmit:
    """Test status submission."""

    @responses.activate
    def test_submit_status_success(self) -> None:
        """Test successful status submission."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            json={
                "success": True,
                "job": {
                    "id": 1,
                    "group_name": "test-group",
                    "name": "test-job",
                    "status": "success",
                    "message": "Test passed",
                },
            },
            status=201,
        )

        client = ApiClient("http://localhost:5000")
        result = client.submit_status("test-group", "test-job", "success", "Test passed")

        assert result["success"] is True
        assert result["job"]["status"] == "success"

    @responses.activate
    def test_submit_status_no_message(self) -> None:
        """Test status submission without message."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        client = ApiClient("http://localhost:5000")
        result = client.submit_status("group", "job", "progress")

        # Verify request body doesn't have message key
        assert "message" not in responses.calls[0].request.body.decode()
        assert result["success"] is True

    @responses.activate
    def test_submit_status_validation_error(self) -> None:
        """Test handling of validation errors."""
        responses.add(
            responses.POST,
            "http://localhost:5000/status",
            json={"error": "Invalid status value"},
            status=400,
        )

        client = ApiClient("http://localhost:5000")
        with pytest.raises(ApiError, match="Invalid status value"):
            client.submit_status("group", "job", "invalid")


class TestApiClientGroups:
    """Test groups endpoints."""

    @responses.activate
    def test_get_groups(self) -> None:
        """Test getting all groups."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups",
            json={
                "groups": [
                    {"id": 1, "name": "group-a", "job_count": 3, "health": "healthy"},
                    {"id": 2, "name": "group-b", "job_count": 2, "health": "unhealthy"},
                ]
            },
            status=200,
        )

        client = ApiClient("http://localhost:5000")
        result = client.get_groups()

        assert len(result["groups"]) == 2
        assert result["groups"][0]["name"] == "group-a"

    @responses.activate
    def test_get_jobs(self) -> None:
        """Test getting jobs in a group."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups/test-group/jobs",
            json={
                "group": {"id": 1, "name": "test-group"},
                "jobs": [
                    {"id": 1, "name": "job-1", "status": "success"},
                    {"id": 2, "name": "job-2", "status": "error"},
                ],
            },
            status=200,
        )

        client = ApiClient("http://localhost:5000")
        result = client.get_jobs("test-group")

        assert result["group"]["name"] == "test-group"
        assert len(result["jobs"]) == 2

    @responses.activate
    def test_get_jobs_not_found(self) -> None:
        """Test 404 when group doesn't exist."""
        responses.add(
            responses.GET,
            "http://localhost:5000/groups/nonexistent/jobs",
            json={"error": "Group not found"},
            status=404,
        )

        client = ApiClient("http://localhost:5000")
        with pytest.raises(NotFoundError, match="Group not found"):
            client.get_jobs("nonexistent")


class TestApiClientConfig:
    """Test config endpoints."""

    @responses.activate
    def test_get_config(self) -> None:
        """Test getting global config."""
        responses.add(
            responses.GET,
            "http://localhost:5000/config",
            json={
                "progress_timeout_minutes": 5,
                "staleness_timeout_hours": 24,
            },
            status=200,
        )

        client = ApiClient("http://localhost:5000")
        result = client.get_config()

        assert result["progress_timeout_minutes"] == 5
        assert result["staleness_timeout_hours"] == 24

    @responses.activate
    def test_update_config(self) -> None:
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

        client = ApiClient("http://localhost:5000")
        result = client.update_config(
            progress_timeout_minutes=10,
            staleness_timeout_hours=48,
        )

        assert result["progress_timeout_minutes"] == 10
        assert result["staleness_timeout_hours"] == 48

    @responses.activate
    def test_get_group_config(self) -> None:
        """Test getting group config."""
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

        client = ApiClient("http://localhost:5000")
        result = client.get_group_config("test-group")

        assert result["group"] == "test-group"
        assert result["progress_timeout_minutes"] is None
        assert result["staleness_timeout_hours"] == 48

    @responses.activate
    def test_update_group_config(self) -> None:
        """Test updating group config."""
        responses.add(
            responses.PUT,
            "http://localhost:5000/groups/test-group/config",
            json={
                "group": "test-group",
                "progress_timeout_minutes": 15,
                "staleness_timeout_hours": None,
            },
            status=200,
        )

        client = ApiClient("http://localhost:5000")
        result = client.update_group_config(
            "test-group",
            progress_timeout_minutes=15,
            reset_staleness_timeout=True,
        )

        assert result["progress_timeout_minutes"] == 15

    @responses.activate
    def test_update_group_config_not_found(self) -> None:
        """Test updating config for nonexistent group."""
        responses.add(
            responses.PUT,
            "http://localhost:5000/groups/nonexistent/config",
            json={"error": "Group not found"},
            status=404,
        )

        client = ApiClient("http://localhost:5000")
        with pytest.raises(NotFoundError):
            client.update_group_config("nonexistent", progress_timeout_minutes=10)


class TestApiClientErrors:
    """Test error handling."""

    @responses.activate
    def test_server_error(self) -> None:
        """Test 500 server error handling."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={"error": "Internal server error"},
            status=500,
        )

        client = ApiClient("http://localhost:5000")
        with pytest.raises(ApiError, match="Internal server error"):
            client.get_health()

    @responses.activate
    def test_invalid_json_response(self) -> None:
        """Test handling of invalid JSON response."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            body="not json",
            status=200,
            content_type="text/plain",
        )

        client = ApiClient("http://localhost:5000")
        with pytest.raises(ApiError, match="Invalid JSON response"):
            client.get_health()


class TestApiClientRetries:
    """Test retry logic for transient failures."""

    @responses.activate
    def test_retry_on_connection_error(self) -> None:
        """Test that connection errors trigger retries."""
        # First two calls fail, third succeeds
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={"status": "healthy"},
            status=200,
        )

        client = ApiClient("http://localhost:5000", retries=2, retry_delay=0.01)
        result = client.get_health()

        assert result["status"] == "healthy"
        assert len(responses.calls) == 3

    @responses.activate
    def test_retry_exhausted(self) -> None:
        """Test that error is raised after all retries exhausted."""
        # All calls fail
        for _ in range(3):
            responses.add(
                responses.GET,
                "http://localhost:5000/health",
                body=requests.exceptions.ConnectionError("Connection refused"),
            )

        client = ApiClient("http://localhost:5000", retries=2, retry_delay=0.01)
        with pytest.raises(StatDashConnectionError, match="Could not connect"):
            client.get_health()

        assert len(responses.calls) == 3

    @responses.activate
    def test_no_retry_on_http_error(self) -> None:
        """Test that HTTP errors are not retried."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            json={"error": "Server error"},
            status=500,
        )

        client = ApiClient("http://localhost:5000", retries=2, retry_delay=0.01)
        with pytest.raises(ApiError, match="Server error"):
            client.get_health()

        # Only one call made (no retries)
        assert len(responses.calls) == 1

    @responses.activate
    def test_no_retry_when_disabled(self) -> None:
        """Test that no retries happen when retries=0."""
        responses.add(
            responses.GET,
            "http://localhost:5000/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        client = ApiClient("http://localhost:5000", retries=0)
        with pytest.raises(StatDashConnectionError):
            client.get_health()

        # Only one call made
        assert len(responses.calls) == 1

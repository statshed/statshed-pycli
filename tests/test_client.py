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
        client = ApiClient("http://localhost:7828")
        assert client.base_url == "http://localhost:7828"
        assert client.timeout == 10

    def test_init_custom_timeout(self) -> None:
        """Test client initialization with custom timeout."""
        client = ApiClient("http://localhost:7828", timeout=30)
        assert client.timeout == 30

    def test_init_strips_trailing_slash(self) -> None:
        """Test that trailing slashes are stripped from base URL."""
        client = ApiClient("http://localhost:7828/")
        assert client.base_url == "http://localhost:7828"

    def test_init_retry_defaults(self) -> None:
        """Test client initialization with default retry settings."""
        client = ApiClient("http://localhost:7828")
        assert client.retries == 0
        assert client.retry_delay == 1.0

    def test_init_custom_retries(self) -> None:
        """Test client initialization with custom retry settings."""
        client = ApiClient("http://localhost:7828", retries=3, retry_delay=0.5)
        assert client.retries == 3
        assert client.retry_delay == 0.5


class TestApiClientHealth:
    """Test health endpoint."""

    @responses.activate
    def test_get_health_healthy(self) -> None:
        """Test getting healthy status."""
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            json={
                "status": "healthy",
                "total_jobs": 5,
                "healthy": 5,
                "by_status": {"success": 5, "error": 0, "progress": 0},
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
        result = client.get_health()

        assert result["status"] == "healthy"
        assert result["total_jobs"] == 5

    @responses.activate
    def test_get_health_connection_error(self) -> None:
        """Test connection error handling."""
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        client = ApiClient("http://localhost:7828")
        with pytest.raises(StatDashConnectionError, match="Could not connect"):
            client.get_health()


class TestApiClientSubmit:
    """Test status submission."""

    @responses.activate
    def test_submit_status_success(self) -> None:
        """Test successful status submission."""
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
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

        client = ApiClient("http://localhost:7828")
        result = client.submit_status("test-group", "test-job", "success", "Test passed")

        assert result["success"] is True
        assert result["job"]["status"] == "success"

    @responses.activate
    def test_submit_status_no_message(self) -> None:
        """Test status submission without message."""
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "progress"}},
            status=201,
        )

        client = ApiClient("http://localhost:7828")
        result = client.submit_status("group", "job", "progress")

        # Verify request body doesn't have message key
        body = responses.calls[0].request.body
        body_str = body.decode() if isinstance(body, bytes) else str(body)
        assert "message" not in body_str
        assert result["success"] is True

    @responses.activate
    def test_submit_status_validation_error(self) -> None:
        """Test handling of validation errors."""
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"error": "Invalid status value"},
            status=400,
        )

        client = ApiClient("http://localhost:7828")
        with pytest.raises(ApiError, match="Invalid status value"):
            client.submit_status("group", "job", "invalid")


class TestApiClientGroups:
    """Test groups endpoints."""

    @responses.activate
    def test_get_groups(self) -> None:
        """Test getting all groups."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups",
            json={
                "groups": [
                    {"id": 1, "name": "group-a", "job_count": 3, "health": "healthy"},
                    {"id": 2, "name": "group-b", "job_count": 2, "health": "unhealthy"},
                ]
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
        result = client.get_groups()

        assert len(result["groups"]) == 2
        assert result["groups"][0]["name"] == "group-a"

    @responses.activate
    def test_get_jobs(self) -> None:
        """Test getting jobs in a group."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/test-group/jobs",
            json={
                "group": {"id": 1, "name": "test-group"},
                "jobs": [
                    {"id": 1, "name": "job-1", "status": "success"},
                    {"id": 2, "name": "job-2", "status": "error"},
                ],
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
        result = client.get_jobs("test-group")

        assert result["group"]["name"] == "test-group"
        assert len(result["jobs"]) == 2

    @responses.activate
    def test_get_jobs_not_found(self) -> None:
        """Test 404 when group doesn't exist."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/nonexistent/jobs",
            json={"error": "Group not found"},
            status=404,
        )

        client = ApiClient("http://localhost:7828")
        with pytest.raises(NotFoundError, match="Group not found"):
            client.get_jobs("nonexistent")


class TestApiClientConfig:
    """Test config endpoints."""

    @responses.activate
    def test_get_config(self) -> None:
        """Test getting global config."""
        responses.add(
            responses.GET,
            "http://localhost:7828/config",
            json={
                "progress_timeout_minutes": 5,
                "staleness_timeout_hours": 24,
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
        result = client.get_config()

        assert result["progress_timeout_minutes"] == 5
        assert result["staleness_timeout_hours"] == 24

    @responses.activate
    def test_update_config(self) -> None:
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

        client = ApiClient("http://localhost:7828")
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

        client = ApiClient("http://localhost:7828")
        result = client.get_group_config("test-group")

        assert result["group"] == "test-group"
        assert result["progress_timeout_minutes"] is None
        assert result["staleness_timeout_hours"] == 48

    @responses.activate
    def test_update_group_config(self) -> None:
        """Test updating group config."""
        responses.add(
            responses.PUT,
            "http://localhost:7828/groups/test-group/config",
            json={
                "group": "test-group",
                "progress_timeout_minutes": 15,
                "staleness_timeout_hours": None,
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
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
            "http://localhost:7828/groups/nonexistent/config",
            json={"error": "Group not found"},
            status=404,
        )

        client = ApiClient("http://localhost:7828")
        with pytest.raises(NotFoundError):
            client.update_group_config("nonexistent", progress_timeout_minutes=10)


class TestApiClientErrors:
    """Test error handling."""

    @responses.activate
    def test_server_error(self) -> None:
        """Test 500 server error handling."""
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            json={"error": "Internal server error"},
            status=500,
        )

        client = ApiClient("http://localhost:7828")
        with pytest.raises(ApiError, match="Internal server error"):
            client.get_health()

    @responses.activate
    def test_invalid_json_response(self) -> None:
        """Test handling of invalid JSON response."""
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            body="not json",
            status=200,
            content_type="text/plain",
        )

        client = ApiClient("http://localhost:7828")
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
            "http://localhost:7828/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            json={"status": "healthy"},
            status=200,
        )

        client = ApiClient("http://localhost:7828", retries=2, retry_delay=0.01)
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
                "http://localhost:7828/health",
                body=requests.exceptions.ConnectionError("Connection refused"),
            )

        client = ApiClient("http://localhost:7828", retries=2, retry_delay=0.01)
        with pytest.raises(StatDashConnectionError, match="Could not connect"):
            client.get_health()

        assert len(responses.calls) == 3

    @responses.activate
    def test_no_retry_on_http_error(self) -> None:
        """Test that HTTP errors are not retried."""
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            json={"error": "Server error"},
            status=500,
        )

        client = ApiClient("http://localhost:7828", retries=2, retry_delay=0.01)
        with pytest.raises(ApiError, match="Server error"):
            client.get_health()

        # Only one call made (no retries)
        assert len(responses.calls) == 1

    @responses.activate
    def test_no_retry_when_disabled(self) -> None:
        """Test that no retries happen when retries=0."""
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        client = ApiClient("http://localhost:7828", retries=0)
        with pytest.raises(StatDashConnectionError):
            client.get_health()

        # Only one call made
        assert len(responses.calls) == 1


class TestApiClientTimeout:
    """Test timeout error handling."""

    @responses.activate
    def test_timeout_error(self) -> None:
        """Test that timeout errors are raised correctly."""
        from statdash_cli.errors import TimeoutError as StatDashTimeoutError

        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            body=requests.exceptions.Timeout("Request timed out"),
        )

        client = ApiClient("http://localhost:7828")
        with pytest.raises(StatDashTimeoutError, match="timed out"):
            client.get_health()

    @responses.activate
    def test_timeout_retry(self) -> None:
        """Test that timeout errors trigger retries."""
        # First two calls timeout, third succeeds
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            body=requests.exceptions.Timeout("Request timed out"),
        )
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            body=requests.exceptions.Timeout("Request timed out"),
        )
        responses.add(
            responses.GET,
            "http://localhost:7828/health",
            json={"status": "healthy"},
            status=200,
        )

        client = ApiClient("http://localhost:7828", retries=2, retry_delay=0.01)
        result = client.get_health()

        assert result["status"] == "healthy"
        assert len(responses.calls) == 3

    @responses.activate
    def test_timeout_exhausted(self) -> None:
        """Test that timeout error is raised after all retries exhausted."""
        from statdash_cli.errors import TimeoutError as StatDashTimeoutError

        # All calls timeout
        for _ in range(3):
            responses.add(
                responses.GET,
                "http://localhost:7828/health",
                body=requests.exceptions.Timeout("Request timed out"),
            )

        client = ApiClient("http://localhost:7828", retries=2, retry_delay=0.01)
        with pytest.raises(StatDashTimeoutError, match="timed out"):
            client.get_health()

        assert len(responses.calls) == 3


class TestApiClientSubmitWithLog:
    """Test status submission with log file upload."""

    @responses.activate
    def test_submit_status_with_log(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test successful status submission with log file."""
        # Create a temporary log file
        log_file = tmp_path / "test.log"  # type: ignore[operator]
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={
                "success": True,
                "job": {
                    "id": 1,
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

        client = ApiClient("http://localhost:7828")
        result = client.submit_status(
            "test-group", "test-job", "success", "Test passed", str(log_file)
        )

        assert result["success"] is True
        assert result["job"]["has_log"] is True

        # Verify multipart request was sent
        request = responses.calls[0].request
        assert "multipart/form-data" in request.headers["Content-Type"]

    @responses.activate
    def test_submit_status_with_log_no_message(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test submission with log but no message."""
        log_file = tmp_path / "test.log"  # type: ignore[operator]
        log_file.write_text("Log content")

        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={
                "success": True,
                "job": {"status": "success", "has_log": True},
            },
            status=201,
        )

        client = ApiClient("http://localhost:7828")
        result = client.submit_status("group", "job", "success", log_path=str(log_file))

        assert result["success"] is True
        # Verify multipart form data fields
        request = responses.calls[0].request
        body = request.body
        # Check that form fields are present in multipart body
        assert b"group" in body
        assert b"job" in body
        assert b"status" in body

    @responses.activate
    def test_submit_with_log_retry_on_connection_error(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Test that retries work correctly with log file uploads."""
        log_file = tmp_path / "test.log"  # type: ignore[operator]
        log_file.write_text("Retry test log")

        # First two calls fail, third succeeds
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )
        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={"success": True, "job": {"status": "success", "has_log": True}},
            status=201,
        )

        client = ApiClient("http://localhost:7828", retries=2, retry_delay=0.01)
        result = client.submit_status("group", "job", "success", log_path=str(log_file))

        assert result["success"] is True
        assert len(responses.calls) == 3

    @responses.activate
    def test_submit_with_log_uploads_disabled_warning(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        """Test that warning is returned when log uploads are disabled."""
        log_file = tmp_path / "test.log"  # type: ignore[operator]
        log_file.write_text("Log content")

        responses.add(
            responses.POST,
            "http://localhost:7828/status",
            json={
                "success": True,
                "job": {"status": "success", "has_log": False},
                "warning": "Log uploads are disabled",
            },
            status=201,
        )

        client = ApiClient("http://localhost:7828")
        result = client.submit_status("group", "job", "success", log_path=str(log_file))

        assert result["success"] is True
        assert result["warning"] == "Log uploads are disabled"


class TestApiClientUrlEncoding:
    """Test URL encoding for special characters."""

    @responses.activate
    def test_get_jobs_with_spaces(self) -> None:
        """Test getting jobs for group with spaces in name."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/my%20group/jobs",
            json={
                "group": {"id": 1, "name": "my group"},
                "jobs": [{"id": 1, "name": "job-1", "status": "success"}],
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
        result = client.get_jobs("my group")

        assert result["group"]["name"] == "my group"

    @responses.activate
    def test_get_jobs_with_slashes(self) -> None:
        """Test getting jobs for group with slashes in name."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/path%2Fto%2Fgroup/jobs",
            json={
                "group": {"id": 1, "name": "path/to/group"},
                "jobs": [],
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
        result = client.get_jobs("path/to/group")

        assert result["group"]["name"] == "path/to/group"

    @responses.activate
    def test_get_group_config_with_special_chars(self) -> None:
        """Test getting group config with special characters."""
        responses.add(
            responses.GET,
            "http://localhost:7828/groups/test%26group/config",
            json={
                "group": "test&group",
                "progress_timeout_minutes": None,
                "staleness_timeout_hours": None,
                "effective_progress_timeout_minutes": 5,
                "effective_staleness_timeout_hours": 24,
            },
            status=200,
        )

        client = ApiClient("http://localhost:7828")
        result = client.get_group_config("test&group")

        assert result["group"] == "test&group"

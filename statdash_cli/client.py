"""API client for StatDash backend.

AIDEV-NOTE: All API interactions go through the ApiClient class.
Errors are converted to StatDash exceptions with appropriate exit codes.
Retry logic handles transient failures (connection errors, timeouts).
"""

import time
from typing import Any
from urllib.parse import quote, urljoin

import requests

from statdash_cli.errors import (
    ApiError,
    ConnectionError,
    NotFoundError,
    TimeoutError,
)


class ApiClient:
    """Client for interacting with the StatDash API.

    AIDEV-NOTE: This client wraps requests and converts HTTP errors
    to StatDash exceptions. All methods can raise:
    - ConnectionError: Server unreachable
    - TimeoutError: Request timed out
    - ApiError: Server returned an error
    - NotFoundError: Resource not found (404)

    Retry logic handles transient failures (connection errors, timeouts)
    when retries > 0. Retries use exponential backoff with jitter.
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        retries: int = 0,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize the API client.

        Args:
            base_url: Base URL of the StatDash API
            timeout: Request timeout in seconds
            retries: Number of retries for transient failures (0 = no retries)
            retry_delay: Base delay between retries in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay

    def _url(self, path: str) -> str:
        """Build full URL for an API path."""
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            path: API path (e.g., "/health")
            json: Optional JSON body for POST/PUT

        Returns:
            Parsed JSON response

        Raises:
            ConnectionError: Server unreachable (after all retries)
            TimeoutError: Request timed out (after all retries)
            ApiError: Server returned an error
            NotFoundError: Resource not found
        """
        url = self._url(path)
        last_error: ConnectionError | TimeoutError | None = None
        response: requests.Response | None = None

        # AIDEV-NOTE: Retry logic only applies to transient failures (connection
        # errors, timeouts). HTTP errors (4xx, 5xx) are not retried as they
        # indicate the request was received but failed.
        for attempt in range(self.retries + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    json=json,
                    timeout=self.timeout,
                )
                # Success - break out of retry loop
                break
            except requests.exceptions.ConnectionError as e:
                last_error = ConnectionError(f"Could not connect to {self.base_url}: {e}")
            except requests.exceptions.Timeout:
                last_error = TimeoutError(f"Request to {url} timed out after {self.timeout}s")
            except requests.exceptions.RequestException as e:
                # Non-transient request error, don't retry
                raise ApiError(f"Request failed: {e}") from e

            # If we have more retries, wait before trying again
            if attempt < self.retries:
                delay = self.retry_delay * (2**attempt)  # Exponential backoff
                time.sleep(delay)
        else:
            # All retries exhausted, raise the last error
            if last_error is not None:
                raise last_error

        # At this point, response must be set (either we got a response or raised)
        assert response is not None

        # Handle HTTP errors
        if response.status_code == 404:
            try:
                error_data = response.json()
                message = error_data.get("error", "Resource not found")
            except (ValueError, KeyError):
                message = "Resource not found"
            raise NotFoundError(message)

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error", f"API error (HTTP {response.status_code})")
            except (ValueError, KeyError):
                message = f"API error (HTTP {response.status_code})"
            raise ApiError(message, status_code=response.status_code)

        try:
            result: dict[str, Any] = response.json()
            return result
        except ValueError as e:
            raise ApiError(f"Invalid JSON response from server: {e}") from e

    def get_health(self) -> dict[str, Any]:
        """Get overall system health.

        Returns:
            Health summary with status counts
        """
        return self._request("GET", "/health")

    def submit_status(
        self,
        group: str,
        job: str,
        status: str,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Submit a job status update.

        Args:
            group: Group name
            job: Job name
            status: Status value (success, error, progress)
            message: Optional status message

        Returns:
            Created/updated job data
        """
        payload: dict[str, Any] = {
            "group": group,
            "job": job,
            "status": status,
        }
        if message:
            payload["message"] = message

        return self._request("POST", "/status", json=payload)

    def get_groups(self) -> dict[str, Any]:
        """Get all groups with health summaries.

        Returns:
            List of groups with status counts
        """
        return self._request("GET", "/groups")

    def get_jobs(self, group_name: str) -> dict[str, Any]:
        """Get all jobs in a group.

        Args:
            group_name: Name of the group

        Returns:
            Group details and list of jobs
        """
        # AIDEV-NOTE: URL-encode group_name to handle special characters safely
        encoded_name = quote(group_name, safe="")
        return self._request("GET", f"/groups/{encoded_name}/jobs")

    def get_config(self) -> dict[str, Any]:
        """Get global configuration.

        Returns:
            Global timeout settings
        """
        return self._request("GET", "/config")

    def update_config(
        self,
        progress_timeout_minutes: int | None = None,
        staleness_timeout_hours: int | None = None,
    ) -> dict[str, Any]:
        """Update global configuration.

        Args:
            progress_timeout_minutes: New progress timeout (optional)
            staleness_timeout_hours: New staleness timeout (optional)

        Returns:
            Updated configuration
        """
        payload: dict[str, Any] = {}
        if progress_timeout_minutes is not None:
            payload["progress_timeout_minutes"] = progress_timeout_minutes
        if staleness_timeout_hours is not None:
            payload["staleness_timeout_hours"] = staleness_timeout_hours

        return self._request("PUT", "/config", json=payload)

    def get_group_config(self, group_name: str) -> dict[str, Any]:
        """Get group-specific configuration.

        Args:
            group_name: Name of the group

        Returns:
            Group configuration with effective values
        """
        encoded_name = quote(group_name, safe="")
        return self._request("GET", f"/groups/{encoded_name}/config")

    def update_group_config(
        self,
        group_name: str,
        progress_timeout_minutes: int | None = None,
        staleness_timeout_hours: int | None = None,
        reset_progress_timeout: bool = False,
        reset_staleness_timeout: bool = False,
    ) -> dict[str, Any]:
        """Update group-specific configuration.

        Args:
            group_name: Name of the group
            progress_timeout_minutes: New progress timeout override
            staleness_timeout_hours: New staleness timeout override
            reset_progress_timeout: Reset to global default
            reset_staleness_timeout: Reset to global default

        Returns:
            Updated group configuration
        """
        payload: dict[str, Any] = {}

        if reset_progress_timeout:
            payload["progress_timeout_minutes"] = None
        elif progress_timeout_minutes is not None:
            payload["progress_timeout_minutes"] = progress_timeout_minutes

        if reset_staleness_timeout:
            payload["staleness_timeout_hours"] = None
        elif staleness_timeout_hours is not None:
            payload["staleness_timeout_hours"] = staleness_timeout_hours

        encoded_name = quote(group_name, safe="")
        return self._request("PUT", f"/groups/{encoded_name}/config", json=payload)

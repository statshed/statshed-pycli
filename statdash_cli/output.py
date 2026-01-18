"""Output formatting for StatDash CLI.

AIDEV-NOTE: This module provides output abstraction. PlainFormatter is
always available; RichFormatter is used when Rich is installed and
output is a TTY. The formatter is selected based on config and environment.
"""

import json
import sys
from abc import ABC, abstractmethod
from typing import Any

# AIDEV-NOTE: Status indicators for plain output. These are simple ASCII/emoji
# that work in any terminal. The Rich formatter uses colored text instead.
STATUS_INDICATORS = {
    "success": "✅",
    "error": "❌",
    "progress": "🔄",
    "timeout": "⏰",
    "stale": "⚠️",
    "healthy": "✅",
    "unhealthy": "❌",
    "in_progress": "🔄",
    "empty": "📭",
}


class OutputFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def health(self, data: dict[str, Any]) -> str:
        """Format health check output."""
        ...

    @abstractmethod
    def groups(self, data: dict[str, Any]) -> str:
        """Format groups list output."""
        ...

    @abstractmethod
    def jobs(self, data: dict[str, Any]) -> str:
        """Format jobs list output."""
        ...

    @abstractmethod
    def config(self, data: dict[str, Any]) -> str:
        """Format global config output."""
        ...

    @abstractmethod
    def group_config(self, data: dict[str, Any]) -> str:
        """Format group config output."""
        ...

    @abstractmethod
    def submit_success(self, data: dict[str, Any]) -> str:
        """Format successful submit output."""
        ...

    @abstractmethod
    def error(self, message: str) -> str:
        """Format error message."""
        ...


class PlainFormatter(OutputFormatter):
    """Plain text output formatter.

    AIDEV-NOTE: This formatter works in any terminal without dependencies.
    It uses simple text formatting with emoji status indicators.
    """

    def health(self, data: dict[str, Any]) -> str:
        """Format health check output."""
        status = data.get("status", "unknown")
        indicator = STATUS_INDICATORS.get(status, "❓")

        lines = [
            f"System Health: {indicator} {status.upper()}",
            f"Total Jobs: {data.get('total_jobs', 0)}",
        ]

        by_status = data.get("by_status", {})
        if by_status:
            lines.append(f"  Success: {by_status.get('success', 0)}")
            lines.append(f"  Error: {by_status.get('error', 0)}")
            lines.append(f"  Progress: {by_status.get('progress', 0)}")
            lines.append(f"  Timeout: {by_status.get('timeout', 0)}")
            lines.append(f"  Stale: {by_status.get('stale', 0)}")

        return "\n".join(lines)

    def groups(self, data: dict[str, Any]) -> str:
        """Format groups list output."""
        groups = data.get("groups", [])
        if not groups:
            return "No groups found."

        lines = []
        for group in groups:
            indicator = STATUS_INDICATORS.get(group.get("health", "unknown"), "❓")
            job_count = group.get("job_count", 0)
            lines.append(f"{indicator} {group['name']} ({job_count} jobs)")

            status_counts = group.get("status_counts", {})
            if status_counts:
                counts = []
                for status in ["success", "error", "progress", "timeout", "stale"]:
                    count = status_counts.get(status, 0)
                    if count > 0:
                        counts.append(f"{status}: {count}")
                if counts:
                    lines.append(f"    {', '.join(counts)}")

        return "\n".join(lines)

    def jobs(self, data: dict[str, Any]) -> str:
        """Format jobs list output."""
        group = data.get("group", {})
        jobs = data.get("jobs", [])

        lines = [f"Group: {group.get('name', 'unknown')}"]

        if not jobs:
            lines.append("  No jobs found.")
            return "\n".join(lines)

        for job in jobs:
            indicator = STATUS_INDICATORS.get(job.get("status", "unknown"), "❓")
            message = job.get("message", "")
            msg_suffix = f" - {message}" if message else ""
            lines.append(f"  {indicator} {job['name']}: {job.get('status', 'unknown')}{msg_suffix}")

        return "\n".join(lines)

    def config(self, data: dict[str, Any]) -> str:
        """Format global config output."""
        return (
            f"Progress Timeout: {data.get('progress_timeout_minutes', 'N/A')} minutes\n"
            f"Staleness Timeout: {data.get('staleness_timeout_hours', 'N/A')} hours"
        )

    def group_config(self, data: dict[str, Any]) -> str:
        """Format group config output."""
        lines = [f"Group: {data.get('group', 'unknown')}"]

        progress = data.get("progress_timeout_minutes")
        effective_progress = data.get("effective_progress_timeout_minutes")
        if progress is None:
            lines.append(f"  Progress Timeout: {effective_progress} minutes (global default)")
        else:
            lines.append(f"  Progress Timeout: {progress} minutes (override)")

        staleness = data.get("staleness_timeout_hours")
        effective_staleness = data.get("effective_staleness_timeout_hours")
        if staleness is None:
            lines.append(f"  Staleness Timeout: {effective_staleness} hours (global default)")
        else:
            lines.append(f"  Staleness Timeout: {staleness} hours (override)")

        return "\n".join(lines)

    def submit_success(self, data: dict[str, Any]) -> str:
        """Format successful submit output."""
        job = data.get("job", {})
        return f"Status submitted: {job.get('group_name', 'unknown')}/{job.get('name', 'unknown')} = {job.get('status', 'unknown')}"

    def error(self, message: str) -> str:
        """Format error message."""
        return f"Error: {message}"


class JsonFormatter(OutputFormatter):
    """JSON output formatter.

    AIDEV-NOTE: This formatter outputs raw JSON for machine consumption.
    Used when --json flag is passed.
    """

    def _format(self, data: dict[str, Any]) -> str:
        return json.dumps(data, indent=2)

    def health(self, data: dict[str, Any]) -> str:
        return self._format(data)

    def groups(self, data: dict[str, Any]) -> str:
        return self._format(data)

    def jobs(self, data: dict[str, Any]) -> str:
        return self._format(data)

    def config(self, data: dict[str, Any]) -> str:
        return self._format(data)

    def group_config(self, data: dict[str, Any]) -> str:
        return self._format(data)

    def submit_success(self, data: dict[str, Any]) -> str:
        return self._format(data)

    def error(self, message: str) -> str:
        return self._format({"error": message})


def get_formatter(output_format: str = "table", color: str = "auto") -> OutputFormatter:
    """Get the appropriate output formatter.

    Args:
        output_format: "table" or "json"
        color: "auto", "always", or "never"

    Returns:
        An OutputFormatter instance
    """
    if output_format == "json":
        return JsonFormatter()

    # For now, always use PlainFormatter
    # Rich support will be added in Phase 3
    return PlainFormatter()


def should_use_color(color: str = "auto") -> bool:
    """Determine if color output should be used.

    Args:
        color: "auto", "always", or "never"

    Returns:
        True if color should be used
    """
    if color == "never":
        return False
    if color == "always":
        return True
    # auto: use color if stdout is a TTY
    return sys.stdout.isatty()

"""Output formatting for StatDash CLI.

AIDEV-NOTE: This module provides output abstraction. PlainFormatter is
always available; RichFormatter is used when Rich is installed and
output is a TTY. The formatter is selected based on config and environment.
"""

from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from io import StringIO
from typing import TYPE_CHECKING, Any

# AIDEV-NOTE: Rich is optional. We check availability at import time and
# only use RichFormatter when Rich is installed. Individual methods import
# Rich classes locally to satisfy type checkers.
RICH_AVAILABLE = False
try:
    import rich  # noqa: F401

    RICH_AVAILABLE = True
except ImportError:
    pass

if TYPE_CHECKING:
    from rich.text import Text

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

        # AIDEV-NOTE: Backend returns 'total', but we also support 'total_jobs' for compatibility
        total = data.get("total", data.get("total_jobs", 0))

        lines = [
            f"System Health: {indicator} {status.upper()}",
            f"Total Jobs: {total}",
        ]

        # AIDEV-NOTE: Backend returns 'counts', but we also support 'by_status' for compatibility
        by_status = data.get("counts", data.get("by_status", {}))
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
            # AIDEV-NOTE: Backend returns 'health_status', but we also support 'health' for compatibility
            health = group.get("health_status", group.get("health", "unknown"))
            indicator = STATUS_INDICATORS.get(health, "❓")
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


# AIDEV-NOTE: Rich color scheme for status indicators. Colors are chosen
# for clear visual distinction: green=good, red=bad, yellow=warning, blue=in progress.
STATUS_COLORS = {
    "success": "green",
    "error": "red",
    "progress": "blue",
    "timeout": "yellow",
    "stale": "yellow",
    "healthy": "green",
    "unhealthy": "red",
    "in_progress": "blue",
    "empty": "dim",
}


class RichFormatter(OutputFormatter):
    """Rich terminal output formatter.

    AIDEV-NOTE: This formatter uses the Rich library for styled output.
    It provides colored status indicators, formatted tables, and panels.
    Falls back to PlainFormatter if Rich is not available.
    """

    def __init__(self) -> None:
        if not RICH_AVAILABLE:
            raise ImportError("Rich library is not installed")
        # Import at runtime to satisfy type checker and ensure availability
        from rich.console import Console

        # Use StringIO to capture output for returning as string
        self._string_io = StringIO()
        self._console: Console = Console(file=self._string_io, force_terminal=True)

    def _reset_output(self) -> None:
        """Reset the string output buffer."""
        from rich.console import Console

        self._string_io = StringIO()
        self._console = Console(file=self._string_io, force_terminal=True)

    def _get_output(self) -> str:
        """Get the output and reset the buffer."""
        result = self._string_io.getvalue().rstrip()
        self._reset_output()
        return result

    def _status_text(self, status: str, text: str | None = None) -> Text:
        """Create colored status text."""
        from rich.text import Text as RichText

        display_text = text if text is not None else status.upper()
        color = STATUS_COLORS.get(status, "white")
        return RichText(display_text, style=color)

    def health(self, data: dict[str, Any]) -> str:
        """Format health check output with colors and panel."""
        from rich.panel import Panel as RichPanel
        from rich.table import Table as RichTable
        from rich.text import Text as RichText

        status = data.get("status", "unknown")
        # AIDEV-NOTE: Backend returns 'total', but we also support 'total_jobs' for compatibility
        total_jobs = data.get("total", data.get("total_jobs", 0))

        # Create status text with color
        status_text = self._status_text(status)

        # Build health summary
        header = RichText("System Health: ", style="bold")
        header.append(status_text)

        self._console.print(RichPanel(header, title="Health Status", border_style="cyan"))

        # Stats table
        table = RichTable(show_header=False, box=None)
        table.add_column("Label", style="dim")
        table.add_column("Value", style="bold")

        table.add_row("Total Jobs", str(total_jobs))

        # AIDEV-NOTE: Backend returns 'counts', but we also support 'by_status' for compatibility
        by_status = data.get("counts", data.get("by_status", {}))
        if by_status:
            for status_name in ["success", "error", "progress", "timeout", "stale"]:
                count = by_status.get(status_name, 0)
                color = STATUS_COLORS.get(status_name, "white")
                table.add_row(f"  {status_name.capitalize()}", RichText(str(count), style=color))

        self._console.print(table)
        return self._get_output()

    def groups(self, data: dict[str, Any]) -> str:
        """Format groups list with styled table."""
        from rich.markup import escape
        from rich.table import Table as RichTable
        from rich.text import Text as RichText

        groups = data.get("groups", [])
        if not groups:
            self._console.print("[dim]No groups found.[/dim]")
            return self._get_output()

        table = RichTable(title="Groups", show_header=True, header_style="bold cyan")
        table.add_column("Status", justify="center", width=8)
        table.add_column("Group Name", style="bold")
        table.add_column("Jobs", justify="right")
        table.add_column("Summary")

        for group in groups:
            # AIDEV-NOTE: Backend returns 'health_status', but we also support 'health' for compatibility
            health = group.get("health_status", group.get("health", "unknown"))
            color = STATUS_COLORS.get(health, "white")
            status_icon = RichText("●", style=color)

            job_count = group.get("job_count", 0)

            # Build status summary
            status_counts = group.get("status_counts", {})
            summary_parts = []
            for status_name in ["success", "error", "progress", "timeout", "stale"]:
                count = status_counts.get(status_name, 0)
                if count > 0:
                    s_color = STATUS_COLORS.get(status_name, "white")
                    summary_parts.append(f"[{s_color}]{status_name}: {count}[/{s_color}]")

            summary = ", ".join(summary_parts) if summary_parts else "[dim]—[/dim]"

            # AIDEV-NOTE: Escape user-provided group names to prevent Rich markup injection
            table.add_row(status_icon, escape(group["name"]), str(job_count), summary)

        self._console.print(table)
        return self._get_output()

    def jobs(self, data: dict[str, Any]) -> str:
        """Format jobs list with styled table."""
        from rich.markup import escape
        from rich.panel import Panel as RichPanel
        from rich.table import Table as RichTable
        from rich.text import Text as RichText

        group = data.get("group", {})
        jobs = data.get("jobs", [])

        group_name = group.get("name", "unknown")
        # AIDEV-NOTE: Escape user-provided group names to prevent Rich markup injection
        safe_group_name = escape(group_name)

        if not jobs:
            self._console.print(
                RichPanel(
                    "[dim]No jobs found.[/dim]",
                    title=f"Group: {safe_group_name}",
                    border_style="cyan",
                )
            )
            return self._get_output()

        table = RichTable(
            title=f"Jobs in '{safe_group_name}'", show_header=True, header_style="bold cyan"
        )
        table.add_column("Status", justify="center", width=8)
        table.add_column("Job Name", style="bold")
        table.add_column("State")
        table.add_column("Message")

        for job in jobs:
            status = job.get("status", "unknown")
            color = STATUS_COLORS.get(status, "white")
            status_icon = RichText("●", style=color)

            # AIDEV-NOTE: Escape user-provided job names and messages to prevent markup injection
            raw_message = job.get("message", "")
            message = escape(raw_message) if raw_message else "[dim]—[/dim]"

            table.add_row(status_icon, escape(job["name"]), RichText(status, style=color), message)

        self._console.print(table)
        return self._get_output()

    def config(self, data: dict[str, Any]) -> str:
        """Format global config output with panel."""
        from rich.panel import Panel as RichPanel
        from rich.table import Table as RichTable

        table = RichTable(show_header=False, box=None)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row(
            "Progress Timeout",
            f"{data.get('progress_timeout_minutes', 'N/A')} minutes",
        )
        table.add_row(
            "Staleness Timeout",
            f"{data.get('staleness_timeout_hours', 'N/A')} hours",
        )

        self._console.print(RichPanel(table, title="Global Configuration", border_style="cyan"))
        return self._get_output()

    def group_config(self, data: dict[str, Any]) -> str:
        """Format group config output with panel."""
        from rich.markup import escape
        from rich.panel import Panel as RichPanel
        from rich.table import Table as RichTable

        group_name = data.get("group", "unknown")
        # AIDEV-NOTE: Escape user-provided group names to prevent Rich markup injection
        safe_group_name = escape(group_name)

        table = RichTable(show_header=False, box=None)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="bold")
        table.add_column("Source", style="dim")

        progress = data.get("progress_timeout_minutes")
        effective_progress = data.get("effective_progress_timeout_minutes")
        if progress is None:
            table.add_row("Progress Timeout", f"{effective_progress} minutes", "(global default)")
        else:
            table.add_row("Progress Timeout", f"{progress} minutes", "(override)")

        staleness = data.get("staleness_timeout_hours")
        effective_staleness = data.get("effective_staleness_timeout_hours")
        if staleness is None:
            table.add_row("Staleness Timeout", f"{effective_staleness} hours", "(global default)")
        else:
            table.add_row("Staleness Timeout", f"{staleness} hours", "(override)")

        self._console.print(
            RichPanel(table, title=f"Group: {safe_group_name}", border_style="cyan")
        )
        return self._get_output()

    def submit_success(self, data: dict[str, Any]) -> str:
        """Format successful submit output."""
        from rich.text import Text as RichText

        job = data.get("job", {})
        group_name = job.get("group_name", "unknown")
        job_name = job.get("name", "unknown")
        status = job.get("status", "unknown")
        color = STATUS_COLORS.get(status, "white")

        text = RichText()
        text.append("✓ ", style="green bold")
        text.append("Status submitted: ", style="dim")
        text.append(f"{group_name}/{job_name}", style="bold")
        text.append(" → ", style="dim")
        text.append(status, style=color)

        self._console.print(text)
        return self._get_output()

    def error(self, message: str) -> str:
        """Format error message with red panel."""
        from rich.panel import Panel as RichPanel
        from rich.text import Text as RichText

        self._console.print(
            RichPanel(
                RichText(message, style="red"),
                title="[red bold]Error[/red bold]",
                border_style="red",
            )
        )
        return self._get_output()


def get_formatter(output_format: str = "table", color: str = "auto") -> OutputFormatter:
    """Get the appropriate output formatter.

    AIDEV-NOTE: Formatter selection logic:
    1. JSON format always returns JsonFormatter
    2. Table format: uses RichFormatter if Rich is available and color is enabled
    3. Falls back to PlainFormatter otherwise

    Args:
        output_format: "table" or "json"
        color: "auto", "always", or "never"

    Returns:
        An OutputFormatter instance
    """
    if output_format == "json":
        return JsonFormatter()

    # Use Rich formatter if available and color is enabled
    if RICH_AVAILABLE and should_use_color(color):
        return RichFormatter()

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

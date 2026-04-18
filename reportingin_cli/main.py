"""Reporting In CLI - Command-line interface entry point.

AIDEV-NOTE: This is the main CLI module using Click. Global options are
defined on the cli() group and passed via context to subcommands.
"""

import contextlib
import os
import re
import select
import sys

import click

from reportingin_cli.client import ApiClient
from reportingin_cli.completion import (
    complete_group_names,
    complete_job_names,
    complete_status_values,
    get_completion_script,
)
from reportingin_cli.config import Config
from reportingin_cli.errors import (
    ConfigError,
    ExitCode,
    NotFoundError,
    ReportingInError,
    get_exit_code,
)
from reportingin_cli.logging import log_submit_error
from reportingin_cli.output import JsonFormatter, OutputFormatter, get_formatter
from reportingin_cli.stream import StreamProcessor, compile_patterns


class Context:
    """CLI context holding configuration and shared objects."""

    def __init__(self) -> None:
        self.config: Config | None = None
        self.client: ApiClient | None = None
        self.quiet: bool = False
        self.json_output: bool = False

    def get_client(self) -> ApiClient:
        """Get or create the API client."""
        if self.client is None:
            assert self.config is not None
            self.client = ApiClient(
                self.config.url,
                timeout=self.config.timeout,
                retries=self.config.retries,
                retry_delay=self.config.retry_delay,
            )
        return self.client

    def get_formatter(self) -> OutputFormatter:
        """Get the output formatter based on config."""
        assert self.config is not None
        return get_formatter(self.config.output_format, self.config.color)

    def output(self, text: str) -> None:
        """Output text unless in quiet mode."""
        if not self.quiet:
            click.echo(text)


pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option(
    "--url",
    "-u",
    envvar="REPORTINGIN_URL",
    help="Reporting In API URL",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    envvar="REPORTINGIN_CONFIG",
    help="Path to config file",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress non-error output",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output in JSON format",
)
@click.version_option(package_name="reportingin-cli")
@pass_context
def cli(
    ctx: Context,
    url: str | None,
    config_path: str | None,
    quiet: bool,
    no_color: bool,
    json_output: bool,
) -> None:
    """Reporting In CLI - Command-line interface for Reporting In status dashboard."""
    try:
        ctx.config = Config.from_sources(
            config_path=config_path,
            cli_url=url,
            cli_no_color=no_color,
            cli_json=json_output,
        )
        ctx.quiet = quiet
        ctx.json_output = json_output
    except ConfigError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(ExitCode.ERROR_CONFIG)


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@pass_context
def health(ctx: Context, json_output: bool) -> None:
    """Check overall system health."""
    try:
        client = ctx.get_client()
        data = client.get_health()

        formatter: OutputFormatter = (
            JsonFormatter() if json_output or ctx.json_output else ctx.get_formatter()
        )
        ctx.output(formatter.health(data))

        # Exit with code 1 if unhealthy
        if data.get("status") in ("unhealthy",):
            sys.exit(ExitCode.ERROR_UNHEALTHY)

    except ReportingInError as e:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command()
@click.option(
    "--group", "-g", required=True, help="Group name", shell_complete=complete_group_names
)
@click.option("--job", "-j", required=True, help="Job name", shell_complete=complete_job_names)
@click.option(
    "--status",
    "-s",
    required=True,
    type=click.Choice(["success", "error", "progress"]),
    help="Status value",
    shell_complete=complete_status_values,
)
@click.option("--message", "-m", help="Optional status message")
@click.option(
    "--log",
    "-l",
    "log_path",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Path to log file to attach",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Exit with error code on failure (default: swallow errors)",
)
@pass_context
def submit(
    ctx: Context,
    group: str,
    job: str,
    status: str,
    message: str | None,
    log_path: str | None,
    strict: bool,
) -> None:
    """Submit a job status update.

    By default, errors are swallowed and the command exits with code 0.
    Use --strict to exit with an error code on failure.

    Optionally attach a log file with --log. If log uploads are disabled
    on the server, the status update still succeeds but a warning is shown.
    """
    assert ctx.config is not None

    # Use strict mode from config unless overridden by CLI
    use_strict = strict or ctx.config.submit.strict

    try:
        client = ctx.get_client()
        data = client.submit_status(group, job, status, message, log_path)

        if not ctx.quiet:
            formatter: OutputFormatter = JsonFormatter() if ctx.json_output else ctx.get_formatter()
            ctx.output(formatter.submit_success(data))

            # AIDEV-NOTE: Backend returns warning field when log uploads are disabled
            # but status update still succeeds. Show this to user as a warning.
            warning = data.get("warning")
            if warning:
                click.echo(f"Warning: {warning}", err=True)

    except ReportingInError as e:
        if use_strict:
            err_formatter: OutputFormatter = ctx.get_formatter()
            click.echo(err_formatter.error(str(e)), err=True)
            sys.exit(get_exit_code(e))
        else:
            # Lenient mode: log error but exit 0
            # Log to syslog if configured, otherwise output warning to stderr
            log_submit_error(e, ctx.config.submit)
            if not ctx.quiet and not ctx.config.submit.syslog:
                click.echo(f"Warning: {e}", err=True)


@cli.command()
@click.option(
    "--group", "-g", required=True, help="Group name", shell_complete=complete_group_names
)
@click.option("--job", "-j", required=True, help="Job name", shell_complete=complete_job_names)
@click.option(
    "--min-time",
    type=click.FloatRange(min=0),
    default=60.0,
    show_default=True,
    help="Minimum seconds between status submissions (debounced, last-wins)",
)
@click.option(
    "--swallow",
    is_flag=True,
    help="Do not echo stdin to stdout",
)
@click.option(
    "--regex",
    "regex_patterns",
    multiple=True,
    metavar="PATTERN",
    help="Only submit lines matching one of these regexes (repeatable)",
)
@click.option(
    "--ignore",
    "ignore_patterns",
    multiple=True,
    metavar="PATTERN",
    help="Skip lines matching one of these regexes (repeatable)",
)
@click.option(
    "--ignore-case",
    is_flag=True,
    help="Case-insensitive regex matching for --regex and --ignore",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Exit with error code on submission failure (default: swallow errors)",
)
@pass_context
def stream(
    ctx: Context,
    group: str,
    job: str,
    min_time: float,
    swallow: bool,
    regex_patterns: tuple[str, ...],
    ignore_patterns: tuple[str, ...],
    ignore_case: bool,
    strict: bool,
) -> None:
    """Stream progress status updates from stdin.

    Each line of stdin is submitted as a "progress" status message to the
    given group/job. Submissions are debounced: the first accepted line is
    sent immediately, and further lines within --min-time are held (last
    message wins) and flushed when the window elapses or on EOF.

    --regex selects which lines are eligible for submission; --ignore
    excludes them. Both use re.search semantics and are repeatable.
    """
    assert ctx.config is not None

    try:
        includes = compile_patterns(regex_patterns, ignore_case)
        excludes = compile_patterns(ignore_patterns, ignore_case)
    except re.error as e:
        click.echo(f"Invalid regex: {e}", err=True)
        sys.exit(ExitCode.ERROR_INVALID_ARGS)

    use_strict = strict or ctx.config.submit.strict
    client = ctx.get_client()
    exit_code = ExitCode.SUCCESS

    def send(message: str) -> None:
        nonlocal exit_code
        try:
            client.submit_status(group, job, "progress", message, None)
        except ReportingInError as e:
            if use_strict:
                err_formatter: OutputFormatter = ctx.get_formatter()
                click.echo(err_formatter.error(str(e)), err=True)
                exit_code = ExitCode(get_exit_code(e))
                raise
            assert ctx.config is not None
            log_submit_error(e, ctx.config.submit)
            if not ctx.quiet and not ctx.config.submit.syslog:
                click.echo(f"Warning: {e}", err=True)

    processor = StreamProcessor(
        min_time=min_time,
        regex_patterns=includes,
        ignore_patterns=excludes,
        send_fn=send,
    )

    try:
        _run_stream_loop(sys.stdin, processor, swallow)
    except ReportingInError:
        # Strict-mode failure already reported; propagate the exit code.
        sys.exit(exit_code)
    except KeyboardInterrupt:
        # Best-effort flush on Ctrl-C; ignore further errors.
        with contextlib.suppress(ReportingInError):
            processor.flush_pending()
        sys.exit(exit_code)


def _run_stream_loop(stdin: object, processor: StreamProcessor, swallow: bool) -> None:
    """Drive the StreamProcessor from ``stdin``.

    AIDEV-NOTE: Real stdin goes through the ``os.read`` path so we can ``select``
    on the raw fd and handle the debounce-flush timeout. Python's BufferedReader
    would read multiple lines into its own buffer on a single syscall, leaving
    ``select`` blind to already-buffered lines; reading raw bytes avoids that.
    When ``stdin`` has no fd (e.g. Click's CliRunner in tests), fall back to
    plain line iteration — no flush timer, but the EOF flush still runs.
    """
    fd = _try_fileno(stdin)
    if fd is None:
        for line in stdin:  # type: ignore[attr-defined]
            _handle_line(line, processor, swallow)
        processor.flush_pending()
        return

    pending_bytes = b""
    while True:
        timeout = processor.time_until_next_flush()
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            processor.flush_if_due()
            continue

        chunk = os.read(fd, 4096)
        if not chunk:
            # EOF: flush any trailing unterminated line, then any pending message.
            if pending_bytes:
                _handle_line(pending_bytes.decode("utf-8", errors="replace"), processor, swallow)
            processor.flush_pending()
            return

        pending_bytes += chunk
        while (newline_idx := pending_bytes.find(b"\n")) != -1:
            line_bytes = pending_bytes[: newline_idx + 1]
            pending_bytes = pending_bytes[newline_idx + 1 :]
            # AIDEV-NOTE: Decode each complete line independently so multi-byte
            # UTF-8 sequences split across os.read boundaries still decode
            # cleanly (a well-formed line contains only complete codepoints).
            _handle_line(line_bytes.decode("utf-8", errors="replace"), processor, swallow)


def _try_fileno(stream: object) -> int | None:
    """Return ``stream.fileno()`` if it points at a real OS fd, else ``None``."""
    try:
        fd: int = stream.fileno()  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        return None
    # AIDEV-NOTE: ``os.fstat`` confirms the fd is a real OS handle. Click's
    # CliRunner wraps stdin in an in-memory stream whose ``fileno`` may raise
    # or point at an unusable fd; ``fstat`` gives us a reliable probe.
    try:
        os.fstat(fd)
    except OSError:
        return None
    return fd


def _handle_line(line: str, processor: StreamProcessor, swallow: bool) -> None:
    if not swallow:
        sys.stdout.write(line)
        sys.stdout.flush()
    processor.process_line(line)


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@pass_context
def groups(ctx: Context, json_output: bool) -> None:
    """List all groups with health summaries."""
    try:
        client = ctx.get_client()
        data = client.get_groups()

        formatter: OutputFormatter = (
            JsonFormatter() if json_output or ctx.json_output else ctx.get_formatter()
        )
        ctx.output(formatter.groups(data))

    except ReportingInError as e:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command()
@click.argument("group_name", shell_complete=complete_group_names)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@pass_context
def jobs(ctx: Context, group_name: str, json_output: bool) -> None:
    """List all jobs in a group."""
    try:
        client = ctx.get_client()
        data = client.get_jobs(group_name)

        formatter: OutputFormatter = (
            JsonFormatter() if json_output or ctx.json_output else ctx.get_formatter()
        )
        ctx.output(formatter.jobs(data))

    except NotFoundError:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(f"Group '{group_name}' not found"), err=True)
        sys.exit(ExitCode.ERROR_NOT_FOUND)
    except ReportingInError as e:
        err_formatter2: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter2.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command("config")
@click.option("--progress-timeout", "-p", type=int, help="Progress timeout in minutes")
@click.option("--staleness-timeout", "-s", type=int, help="Staleness timeout in hours")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@pass_context
def config_cmd(
    ctx: Context,
    progress_timeout: int | None,
    staleness_timeout: int | None,
    json_output: bool,
) -> None:
    """View or update global configuration.

    Without options, displays current configuration.
    With options, updates the specified values.
    """
    try:
        client = ctx.get_client()

        # If any option is provided, update config
        if progress_timeout is not None or staleness_timeout is not None:
            data = client.update_config(
                progress_timeout_minutes=progress_timeout,
                staleness_timeout_hours=staleness_timeout,
            )
        else:
            data = client.get_config()

        formatter: OutputFormatter = (
            JsonFormatter() if json_output or ctx.json_output else ctx.get_formatter()
        )
        ctx.output(formatter.config(data))

    except ReportingInError as e:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command("group-config")
@click.argument("group_name", shell_complete=complete_group_names)
@click.option("--progress-timeout", "-p", type=int, help="Progress timeout override (minutes)")
@click.option("--staleness-timeout", "-s", type=int, help="Staleness timeout override (hours)")
@click.option("--reset-progress-timeout", is_flag=True, help="Reset to global default")
@click.option("--reset-staleness-timeout", is_flag=True, help="Reset to global default")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@pass_context
def group_config_cmd(
    ctx: Context,
    group_name: str,
    progress_timeout: int | None,
    staleness_timeout: int | None,
    reset_progress_timeout: bool,
    reset_staleness_timeout: bool,
    json_output: bool,
) -> None:
    """View or update group-specific configuration.

    Without options, displays current group configuration.
    With options, updates the specified values.
    Use --reset-* options to revert to global defaults.
    """
    try:
        client = ctx.get_client()

        # If any option is provided, update config
        if (
            progress_timeout is not None
            or staleness_timeout is not None
            or reset_progress_timeout
            or reset_staleness_timeout
        ):
            data = client.update_group_config(
                group_name,
                progress_timeout_minutes=progress_timeout,
                staleness_timeout_hours=staleness_timeout,
                reset_progress_timeout=reset_progress_timeout,
                reset_staleness_timeout=reset_staleness_timeout,
            )
        else:
            data = client.get_group_config(group_name)

        formatter: OutputFormatter = (
            JsonFormatter() if json_output or ctx.json_output else ctx.get_formatter()
        )
        ctx.output(formatter.group_config(data))

    except NotFoundError:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(f"Group '{group_name}' not found"), err=True)
        sys.exit(ExitCode.ERROR_NOT_FOUND)
    except ReportingInError as e:
        err_formatter2: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter2.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell: str) -> None:
    """Generate shell completion script.

    Outputs a completion script for the specified shell.
    Install by redirecting output to the appropriate location:

    \b
    Bash: reportingin-cli completion bash > ~/.local/share/bash-completion/completions/reportingin-cli
    Zsh:  reportingin-cli completion zsh > ~/.zfunc/_reportingin-cli
    Fish: reportingin-cli completion fish > ~/.config/fish/completions/reportingin-cli.fish
    """
    script = get_completion_script(shell)
    click.echo(script)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()

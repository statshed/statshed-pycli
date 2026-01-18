"""StatDash CLI - Command-line interface entry point.

AIDEV-NOTE: This is the main CLI module using Click. Global options are
defined on the cli() group and passed via context to subcommands.
"""

import sys

import click

from statdash_cli.client import ApiClient
from statdash_cli.completion import get_completion_script
from statdash_cli.config import Config
from statdash_cli.errors import (
    ConfigError,
    ExitCode,
    NotFoundError,
    StatDashError,
    get_exit_code,
)
from statdash_cli.output import JsonFormatter, OutputFormatter, get_formatter


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
            self.client = ApiClient(self.config.url, self.config.timeout)
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
    envvar="STATDASH_URL",
    help="StatDash API URL",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    envvar="STATDASH_CONFIG",
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
@click.version_option(package_name="statdash-cli")
@pass_context
def cli(
    ctx: Context,
    url: str | None,
    config_path: str | None,
    quiet: bool,
    no_color: bool,
    json_output: bool,
) -> None:
    """StatDash CLI - Command-line interface for StatDash status dashboard."""
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

        formatter: OutputFormatter
        if json_output or ctx.json_output:
            formatter = JsonFormatter()
        else:
            formatter = ctx.get_formatter()

        ctx.output(formatter.health(data))

        # Exit with code 1 if unhealthy
        if data.get("status") in ("unhealthy",):
            sys.exit(ExitCode.ERROR_UNHEALTHY)

    except StatDashError as e:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command()
@click.option("--group", "-g", required=True, help="Group name")
@click.option("--job", "-j", required=True, help="Job name")
@click.option(
    "--status",
    "-s",
    required=True,
    type=click.Choice(["success", "error", "progress"]),
    help="Status value",
)
@click.option("--message", "-m", help="Optional status message")
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
    strict: bool,
) -> None:
    """Submit a job status update.

    By default, errors are swallowed and the command exits with code 0.
    Use --strict to exit with an error code on failure.
    """
    assert ctx.config is not None

    # Use strict mode from config unless overridden by CLI
    use_strict = strict or ctx.config.submit.strict

    try:
        client = ctx.get_client()
        data = client.submit_status(group, job, status, message)

        if not ctx.quiet:
            formatter: OutputFormatter
            if ctx.json_output:
                formatter = JsonFormatter()
            else:
                formatter = ctx.get_formatter()
            ctx.output(formatter.submit_success(data))

    except StatDashError as e:
        if use_strict:
            err_formatter: OutputFormatter = ctx.get_formatter()
            click.echo(err_formatter.error(str(e)), err=True)
            sys.exit(get_exit_code(e))
        else:
            # Lenient mode: log error but exit 0
            # AIDEV-NOTE: Syslog support will be added in Phase 2
            if not ctx.quiet:
                click.echo(f"Warning: {e}", err=True)


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@pass_context
def groups(ctx: Context, json_output: bool) -> None:
    """List all groups with health summaries."""
    try:
        client = ctx.get_client()
        data = client.get_groups()

        formatter: OutputFormatter
        if json_output or ctx.json_output:
            formatter = JsonFormatter()
        else:
            formatter = ctx.get_formatter()

        ctx.output(formatter.groups(data))

    except StatDashError as e:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command()
@click.argument("group_name")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@pass_context
def jobs(ctx: Context, group_name: str, json_output: bool) -> None:
    """List all jobs in a group."""
    try:
        client = ctx.get_client()
        data = client.get_jobs(group_name)

        formatter: OutputFormatter
        if json_output or ctx.json_output:
            formatter = JsonFormatter()
        else:
            formatter = ctx.get_formatter()

        ctx.output(formatter.jobs(data))

    except NotFoundError:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(f"Group '{group_name}' not found"), err=True)
        sys.exit(ExitCode.ERROR_NOT_FOUND)
    except StatDashError as e:
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

        formatter: OutputFormatter
        if json_output or ctx.json_output:
            formatter = JsonFormatter()
        else:
            formatter = ctx.get_formatter()

        ctx.output(formatter.config(data))

    except StatDashError as e:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(str(e)), err=True)
        sys.exit(get_exit_code(e))


@cli.command("group-config")
@click.argument("group_name")
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

        formatter: OutputFormatter
        if json_output or ctx.json_output:
            formatter = JsonFormatter()
        else:
            formatter = ctx.get_formatter()

        ctx.output(formatter.group_config(data))

    except NotFoundError:
        err_formatter: OutputFormatter = ctx.get_formatter()
        click.echo(err_formatter.error(f"Group '{group_name}' not found"), err=True)
        sys.exit(ExitCode.ERROR_NOT_FOUND)
    except StatDashError as e:
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
    Bash: statdash-cli completion bash > ~/.local/share/bash-completion/completions/statdash-cli
    Zsh:  statdash-cli completion zsh > ~/.zfunc/_statdash-cli
    Fish: statdash-cli completion fish > ~/.config/fish/completions/statdash-cli.fish
    """
    script = get_completion_script(shell)
    click.echo(script)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()

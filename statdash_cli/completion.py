"""Shell completion utilities for StatDash CLI.

AIDEV-NOTE: This module provides shell completion script generation and
dynamic completions for group/job names. The dynamic completions query
the API silently (failing gracefully) to provide contextual suggestions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem


# AIDEV-NOTE: Click provides built-in shell completion. These templates
# extend the basic completion with StatDash-specific enhancements.

BASH_COMPLETION_SCRIPT = """
# StatDash CLI Bash completion
# Install: statdash-cli completion bash > ~/.local/share/bash-completion/completions/statdash-cli

_statdash_cli_completion() {
    local IFS=$'\\n'
    local response

    response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD=$COMP_CWORD _STATDASH_CLI_COMPLETE=bash_complete $1)

    for completion in $response; do
        IFS=',' read type value <<< "$completion"
        COMPREPLY+=($value)
    done

    return 0
}

complete -o default -F _statdash_cli_completion statdash-cli
"""

ZSH_COMPLETION_SCRIPT = """
#compdef statdash-cli
# StatDash CLI Zsh completion
# Install: statdash-cli completion zsh > ~/.zfunc/_statdash-cli

_statdash_cli() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[statdash-cli] )) && return 1

    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _STATDASH_CLI_COMPLETE=zsh_complete statdash-cli)}")

    for key descr in ${(kv)response}; do
        if [[ "$descr" == "_" ]]; then
            completions+=("$key")
        else
            completions_with_descriptions+=("$key":"$descr")
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

compdef _statdash_cli statdash-cli
"""

FISH_COMPLETION_SCRIPT = """
# StatDash CLI Fish completion
# Install: statdash-cli completion fish > ~/.config/fish/completions/statdash-cli.fish

function _statdash_cli_completion
    set -l response (env _STATDASH_CLI_COMPLETE=fish_complete COMP_WORDS=(commandline -cp) COMP_CWORD=(commandline -t) statdash-cli)

    for completion in $response
        set -l metadata (string split "," -- $completion)

        if [ $metadata[1] = "dir" ]
            __fish_complete_directories $metadata[2]
        else if [ $metadata[1] = "file" ]
            __fish_complete_path $metadata[2]
        else if [ $metadata[1] = "plain" ]
            echo $metadata[2]
        end
    end
end

complete -c statdash-cli -f -a "(_statdash_cli_completion)"
"""


def get_completion_script(shell: str) -> str:
    """Get the completion script for a shell.

    Args:
        shell: Shell name (bash, zsh, fish)

    Returns:
        Completion script content

    Raises:
        click.BadParameter: If shell is not supported
    """
    scripts = {
        "bash": BASH_COMPLETION_SCRIPT,
        "zsh": ZSH_COMPLETION_SCRIPT,
        "fish": FISH_COMPLETION_SCRIPT,
    }

    if shell not in scripts:
        raise click.BadParameter(f"Unsupported shell: {shell}. Supported shells: bash, zsh, fish")

    return scripts[shell].strip()


# AIDEV-NOTE: Dynamic completion functions query the API to get suggestions.
# They fail silently (return empty list) if the API is unavailable, so
# completion still works even without a running server.


def _get_api_url() -> str:
    """Get the API URL from environment or config, falling back to default.

    This is a lightweight check for completion - we don't load the full config.
    """
    import os

    from statdash_cli.config import DEFAULT_URL

    return os.environ.get("STATDASH_URL", DEFAULT_URL)


def complete_group_names(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Provide completion for group names.

    Queries the API to get a list of groups and filters by the incomplete text.
    Fails silently if the API is unavailable.

    Args:
        ctx: Click context
        param: Click parameter
        incomplete: The partial text being completed

    Returns:
        List of completion items for matching group names
    """
    from click.shell_completion import CompletionItem

    try:
        import requests

        url = _get_api_url()
        response = requests.get(f"{url}/api/groups", timeout=2)
        response.raise_for_status()
        data = response.json()

        groups = data.get("groups", [])
        completions = []
        for group in groups:
            name = group.get("name", "")
            if name.startswith(incomplete):
                health = group.get("health", "")
                job_count = group.get("job_count", 0)
                help_text = f"{health}, {job_count} jobs"
                completions.append(CompletionItem(name, help=help_text))
        return completions
    except Exception:
        # Silently fail - completion should not break on API errors
        return []


def complete_job_names(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Provide completion for job names within a group.

    Looks for the --group or -g option in the context to determine which
    group to query jobs from. Fails silently if the API is unavailable.

    Args:
        ctx: Click context
        param: Click parameter
        incomplete: The partial text being completed

    Returns:
        List of completion items for matching job names
    """
    from click.shell_completion import CompletionItem

    try:
        from urllib.parse import quote

        import requests

        # Find the group name from the command context
        # Check params for --group or -g
        group_name = None
        if ctx.params:
            group_name = ctx.params.get("group")

        if not group_name:
            return []

        url = _get_api_url()
        encoded_group = quote(group_name, safe="")
        response = requests.get(f"{url}/api/groups/{encoded_group}/jobs", timeout=2)
        response.raise_for_status()
        data = response.json()

        jobs = data.get("jobs", [])
        completions = []
        for job in jobs:
            name = job.get("name", "")
            if name.startswith(incomplete):
                status = job.get("status", "")
                completions.append(CompletionItem(name, help=status))
        return completions
    except Exception:
        # Silently fail - completion should not break on API errors
        return []


def complete_status_values(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Provide completion for status values.

    Args:
        ctx: Click context
        param: Click parameter
        incomplete: The partial text being completed

    Returns:
        List of completion items for status values
    """
    from click.shell_completion import CompletionItem

    statuses = [
        ("success", "Job completed successfully"),
        ("error", "Job encountered an error"),
        ("progress", "Job is currently running"),
    ]

    return [
        CompletionItem(status, help=desc)
        for status, desc in statuses
        if status.startswith(incomplete)
    ]

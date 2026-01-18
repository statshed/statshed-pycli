"""Shell completion utilities for StatDash CLI.

AIDEV-NOTE: This module provides shell completion script generation.
Dynamic completions (group/job names from API) will be added in Phase 3.
"""

import click

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

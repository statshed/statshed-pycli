# StatDash CLI

Command-line interface for the StatDash status dashboard.

## Installation

```bash
pip install statdash-cli
```

For rich terminal output:
```bash
pip install statdash-cli[rich]
```

## Usage

### Submit Job Status

```bash
# Submit a success status
statdash-cli submit -g nightly-builds -j backend-tests -s success -m "All tests passed"

# Submit an error status
statdash-cli submit -g nightly-builds -j backend-tests -s error -m "3 tests failed"

# Submit a progress status
statdash-cli submit -g nightly-builds -j backend-tests -s progress -m "Running tests..."
```

### Check System Health

```bash
statdash-cli health
```

### List Groups

```bash
statdash-cli groups
```

### List Jobs in a Group

```bash
statdash-cli jobs nightly-builds
```

### View/Update Configuration

```bash
# View global config
statdash-cli config

# Update global config
statdash-cli config --progress-timeout 10 --staleness-timeout 48

# View group config
statdash-cli group-config nightly-builds

# Update group config
statdash-cli group-config nightly-builds --progress-timeout 15
```

## Configuration File

The CLI reads configuration from these locations (in order of precedence):

1. Path specified via `--config` or `STATDASH_CONFIG` environment variable
2. `./statdash-cli.yaml` (current directory)
3. `~/.config/statdash/config.yaml`
4. `/etc/statdash/config.yaml`

Example configuration:

```yaml
url: http://localhost:5000
output_format: table
color: auto
timeout: 10

submit:
  syslog: false
  strict: false
```

## Environment Variables

- `STATDASH_URL`: API server URL
- `STATDASH_CONFIG`: Path to configuration file
- `NO_COLOR`: Disable colored output

## Exit Codes

| Code | Description |
|------|-------------|
| 0 | Success |
| 1 | Health check returned unhealthy status |
| 2 | API error |
| 3 | Connection error |
| 4 | Timeout error |
| 5 | Configuration error |
| 10 | Invalid arguments |
| 11 | Resource not found |

## Shell Completion

StatDash CLI provides shell completion for Bash, Zsh, and Fish. The completion includes:

- Command and option names
- Dynamic group name completion (queries the API)
- Dynamic job name completion (when group is specified)
- Status value completion (`success`, `error`, `progress`)

### Installation

**Bash:**
```bash
# Create the completions directory if it doesn't exist
mkdir -p ~/.local/share/bash-completion/completions

# Generate and install the completion script
statdash-cli completion bash > ~/.local/share/bash-completion/completions/statdash-cli

# Reload your shell or source the file
source ~/.local/share/bash-completion/completions/statdash-cli
```

**Zsh:**
```bash
# Create the completions directory if it doesn't exist
mkdir -p ~/.zfunc

# Add to .zshrc if not already present:
# fpath+=~/.zfunc
# autoload -Uz compinit && compinit

# Generate and install the completion script
statdash-cli completion zsh > ~/.zfunc/_statdash-cli

# Reload completions
autoload -Uz compinit && compinit
```

**Fish:**
```bash
# Create the completions directory if it doesn't exist
mkdir -p ~/.config/fish/completions

# Generate and install the completion script
statdash-cli completion fish > ~/.config/fish/completions/statdash-cli.fish
```

### Dynamic Completion

The shell completion queries the StatDash API to provide contextual suggestions:

- When completing group names (`--group` or group arguments), available groups are fetched from the server
- When completing job names (`--job`), jobs from the specified group are fetched
- If the server is unavailable, completion falls back to basic suggestions

Set `STATDASH_URL` environment variable if your server is not at the default location:
```bash
export STATDASH_URL=https://statdash.example.com
```

## Development

```bash
# Install development dependencies
uv sync --extra dev

# Run tests
pytest

# Format code
ruff format .

# Type check
mypy statdash_cli
```

## License

MIT

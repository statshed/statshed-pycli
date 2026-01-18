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

```bash
# Bash
statdash-cli completion bash > ~/.local/share/bash-completion/completions/statdash-cli

# Zsh
statdash-cli completion zsh > ~/.zfunc/_statdash-cli

# Fish
statdash-cli completion fish > ~/.config/fish/completions/statdash-cli.fish
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

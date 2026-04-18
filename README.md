# Reporting In CLI

[![Tests](https://github.com/reportingin/reportingin-cli/actions/workflows/test.yml/badge.svg)](https://github.com/reportingin/reportingin-cli/actions/workflows/test.yml)

Command-line interface for the Reporting In status dashboard.

## Installation

```bash
pip install reportingin-cli
```

For rich terminal output:
```bash
pip install reportingin-cli[rich]
```

## Usage

### Submit Job Status

```bash
# Submit a success status
reportingin submit -g nightly-builds -j backend-tests -s success -m "All tests passed"

# Submit an error status
reportingin submit -g nightly-builds -j backend-tests -s error -m "3 tests failed"

# Submit a progress status
reportingin submit -g nightly-builds -j backend-tests -s progress -m "Running tests..."
```

### Check System Health

```bash
reportingin health
```

### List Groups

```bash
reportingin groups
```

### List Jobs in a Group

```bash
reportingin jobs nightly-builds
```

### View/Update Configuration

```bash
# View global config
reportingin config

# Update global config
reportingin config --progress-timeout 10 --staleness-timeout 48

# View group config
reportingin group-config nightly-builds

# Update group config
reportingin group-config nightly-builds --progress-timeout 15
```

## Configuration File

The CLI reads configuration from these locations (in order of precedence):

1. Path specified via `--config` or `REPORTINGIN_CONFIG` environment variable
2. `./reportingin.yaml` (current directory)
3. `~/.config/reportingin/reportingin.yaml`
4. `/etc/reportingin/reportingin.yaml`

Example configuration:

```yaml
url: http://localhost:7828
output_format: table
color: auto
timeout: 10

submit:
  syslog: false
  strict: false
```

## Environment Variables

- `REPORTINGIN_URL`: API server URL
- `REPORTINGIN_CONFIG`: Path to configuration file
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

Reporting In CLI provides shell completion for Bash, Zsh, and Fish. The completion includes:

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
reportingin completion bash > ~/.local/share/bash-completion/completions/reportingin

# Reload your shell or source the file
source ~/.local/share/bash-completion/completions/reportingin
```

**Zsh:**
```bash
# Create the completions directory if it doesn't exist
mkdir -p ~/.zfunc

# Add to .zshrc if not already present:
# fpath+=~/.zfunc
# autoload -Uz compinit && compinit

# Generate and install the completion script
reportingin completion zsh > ~/.zfunc/_reportingin

# Reload completions
autoload -Uz compinit && compinit
```

**Fish:**
```bash
# Create the completions directory if it doesn't exist
mkdir -p ~/.config/fish/completions

# Generate and install the completion script
reportingin completion fish > ~/.config/fish/completions/reportingin.fish
```

### Dynamic Completion

The shell completion queries the Reporting In API to provide contextual suggestions:

- When completing group names (`--group` or group arguments), available groups are fetched from the server
- When completing job names (`--job`), jobs from the specified group are fetched
- If the server is unavailable, completion falls back to basic suggestions

Set `REPORTINGIN_URL` environment variable if your server is not at the default location:
```bash
export REPORTINGIN_URL=https://reportingin.example.com
```

## Common Use Cases

### CI/CD Pipeline (GitHub Actions)

```yaml
jobs:
  build:
    steps:
      - name: Report build start
        run: |
          reportingin submit -g ci-builds -j "${{ github.repository }}" \
            -s progress -m "Build started: ${{ github.sha }}"

      - name: Build
        run: make build

      - name: Report build success
        if: success()
        run: |
          reportingin submit -g ci-builds -j "${{ github.repository }}" \
            -s success -m "Build passed: ${{ github.sha }}"

      - name: Report build failure
        if: failure()
        run: |
          reportingin submit -g ci-builds -j "${{ github.repository }}" \
            -s error -m "Build failed: ${{ github.sha }}"
```

### Cron Job Status Reporting

For safe use with `set -eu` (script exits on error), use the default lenient mode:

```bash
#!/bin/bash
set -eu

# Submit commands won't cause script to exit on API errors
reportingin submit -g backups -j database -s progress -m "Starting backup"

# Do the actual backup
pg_dump mydb > /backups/mydb.sql

# Report success
reportingin submit -g backups -j database -s success -m "Backup completed"
```

For manual error handling with strict mode:

```bash
#!/bin/bash

if ! reportingin submit --strict -g backups -j database -s progress; then
    echo "Warning: Could not report status to dashboard"
fi

pg_dump mydb > /backups/mydb.sql
backup_status=$?

if [ $backup_status -eq 0 ]; then
    reportingin submit -g backups -j database -s success
else
    reportingin submit -g backups -j database -s error -m "Backup failed with code $backup_status"
fi
```

### Interactive Terminal Usage

```bash
# Check overall health with rich output
$ reportingin health

# List groups with status summary
$ reportingin groups

# Drill into a specific group
$ reportingin jobs nightly-builds

# Check group-specific timeout configuration
$ reportingin group-config nightly-builds

# Update group timeout (builds can take longer)
$ reportingin group-config nightly-builds --progress-timeout 30
```

### Script Integration with Error Logging to Syslog

Enable syslog logging for daemon/cron scenarios where stderr may not be monitored:

```yaml
# ~/.config/reportingin/reportingin.yaml
url: https://reportingin.example.com
submit:
  syslog: true
  syslog_facility: local0
```

## Troubleshooting

### Connection Refused

```
Error: Could not connect to http://localhost:7828: Connection refused
```

**Cause**: The Reporting In backend is not running or is running on a different port.

**Solution**:
- Verify the backend is running: `curl http://localhost:7828/health`
- Check the URL with `--url` or in config file
- Set `REPORTINGIN_URL` environment variable

### Request Timeout

```
Error: Request to http://localhost:7828/health timed out after 10s
```

**Cause**: The server is slow or unresponsive.

**Solution**:
- Increase timeout in config file: `timeout: 30`
- Check server health and load
- Enable retries: `retries: 3`

### Group/Job Not Found

```
Error: Group 'nonexistent' not found
```

**Cause**: The group doesn't exist in the database.

**Solution**:
- Groups are auto-created on first status submission
- Submit a status to create the group: `reportingin submit -g newgroup -j newjob -s success`

### Invalid Configuration File

```
Configuration error: Invalid YAML in config file ...
```

**Cause**: The YAML config file has syntax errors.

**Solution**:
- Validate your YAML with a linter
- Check for proper indentation (spaces, not tabs)
- Ensure string values are properly quoted if they contain special characters

### Shell Completion Not Working

**Cause**: Completion script not installed or shell not reloaded.

**Solution**:
1. Regenerate the completion script for your shell
2. Ensure it's in the correct location (see Shell Completion section)
3. Reload your shell or source the script

## Development

```bash
# Install development dependencies
uv sync --extra dev

# Run tests
pytest

# Run tests with coverage
pytest --cov=reportingin_cli

# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy reportingin_cli
```

## Building a Debian Package

### Building the Package

From the project root directory:

```bash
# Build the package (binary only, no source package signing)
dpkg-buildpackage -us -uc -b

# Or use debuild for a cleaner build environment
debuild -us -uc -b
```

The built `.deb` file will be placed in the parent directory (`../`).

### Installing the Package

```bash
sudo dpkg -i ../reportingin-cli_*.deb

# Install any missing dependencies
sudo apt install -f
```

### Updating the Version

Before building a new release, update `debian/changelog`:

```bash
# Add a new changelog entry (interactive)
dch -i

# Or specify the new version directly
dch -v 1.0.3-1 "Description of changes"
```
```

## License

CC0-1.0 (Public Domain Dedication)

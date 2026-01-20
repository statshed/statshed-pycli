# StatDash CLI - Design Document

A command-line interface for interacting with the StatDash status dashboard API.

## Overview

The StatDash CLI (`statdash-cli`) provides a robust command-line interface for submitting job statuses and querying the StatDash dashboard. It is designed to work equally well in interactive terminal sessions, CI/CD pipelines, cron jobs, and shell scripts.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| CLI Framework | Click |
| HTTP Client | Requests |
| Configuration | PyYAML |
| Rich Output | Rich (optional) |
| Package Manager | uv |
| Linting/Formatting | Ruff, mypy |

## Project Structure

```
cli/
├── statdash_cli/
│   ├── __init__.py
│   ├── main.py              # CLI entry point and commands
│   ├── client.py            # API client
│   ├── config.py            # Configuration file handling
│   ├── output.py            # Output formatting (plain/rich)
│   ├── errors.py            # Error handling and exit codes
│   └── completion.py        # Shell completion utilities
├── tests/
│   ├── __init__.py
│   ├── test_client.py
│   ├── test_commands.py
│   ├── test_config.py
│   └── test_output.py
├── pyproject.toml
└── README.md
```

## Command Reference

### Global Options

| Option | Short | Environment Variable | Description |
|--------|-------|---------------------|-------------|
| `--url` | `-u` | `STATDASH_URL` | StatDash API URL (default: from config or `http://localhost:7828`) |
| `--config` | `-c` | `STATDASH_CONFIG` | Path to config file |
| `--quiet` | `-q` | - | Suppress non-error output |
| `--no-color` | - | `NO_COLOR` | Disable colored output |
| `--json` | - | - | Output in JSON format (where applicable) |

### Commands

#### `submit` - Submit Job Status

```bash
statdash-cli submit --group <name> --job <name> --status <status> [--message <msg>]
```

| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| `--group` | `-g` | Yes | Group name |
| `--job` | `-j` | Yes | Job name |
| `--status` | `-s` | Yes | Status: `success`, `error`, `progress` |
| `--message` | `-m` | No | Optional status message |
| `--strict` | - | No | Exit with error code on failure (default: swallow errors) |

**Error Handling Modes:**

- **Default (lenient)**: Errors are logged (optionally to syslog) but exit code is 0. Safe for use in scripts with `set -eu`.
- **Strict (`--strict`)**: Errors produce non-zero exit codes and error output.

#### `health` - System Health Summary

```bash
statdash-cli health [--json]
```

Returns overall system health status. Exits with code 1 if unhealthy.

#### `groups` - List Groups

```bash
statdash-cli groups [--json]
```

Lists all groups with health summaries.

#### `jobs` - List Jobs in Group

```bash
statdash-cli jobs <group_name> [--json]
```

Lists all jobs within a specific group.

#### `config` - Global Configuration

```bash
# View global config
statdash-cli config

# Update global config
statdash-cli config --progress-timeout <minutes> --staleness-timeout <hours>
```

| Option | Short | Description |
|--------|-------|-------------|
| `--progress-timeout` | `-p` | Progress timeout in minutes |
| `--staleness-timeout` | `-s` | Staleness timeout in hours |
| `--json` | - | Output as JSON |

#### `group-config` - Group-Specific Configuration

```bash
# View group config
statdash-cli group-config <group_name>

# Update group config
statdash-cli group-config <group_name> --progress-timeout <minutes>

# Reset to global defaults
statdash-cli group-config <group_name> --reset-progress-timeout --reset-staleness-timeout
```

| Option | Short | Description |
|--------|-------|-------------|
| `--progress-timeout` | `-p` | Override progress timeout (minutes) |
| `--staleness-timeout` | `-s` | Override staleness timeout (hours) |
| `--reset-progress-timeout` | - | Reset to global default |
| `--reset-staleness-timeout` | - | Reset to global default |
| `--json` | - | Output as JSON |

#### `completion` - Shell Completion

```bash
# Generate completion script
statdash-cli completion bash > ~/.local/share/bash-completion/completions/statdash-cli
statdash-cli completion zsh > ~/.zfunc/_statdash-cli
statdash-cli completion fish > ~/.config/fish/completions/statdash-cli.fish
```

## Configuration File

The CLI reads configuration from the following locations (in order of precedence):

1. Path specified via `--config` or `STATDASH_CONFIG`
2. `./statdash-cli.yaml` (current directory)
3. `~/.config/statdash/statdash.yaml`
4. `/etc/statdash/statdash.yaml`

### Configuration Schema

```yaml
# StatDash CLI Configuration

# API server URL
url: http://localhost:7828

# Default output format: "table" or "json"
output_format: table

# Enable colored/rich output (true/false/auto)
# "auto" enables color when stdout is a TTY
color: auto

# Submit command behavior
submit:
  # Log errors to syslog instead of stderr
  syslog: false

  # Syslog facility (if syslog is enabled)
  syslog_facility: user

  # Default to strict mode (exit with error codes)
  strict: false

# Request timeout in seconds
timeout: 10
```

## Exit Codes

| Code | Name | Description |
|------|------|-------------|
| 0 | SUCCESS | Command completed successfully |
| 1 | ERROR_UNHEALTHY | Health check returned unhealthy status |
| 2 | ERROR_API | API returned an error response |
| 3 | ERROR_CONNECTION | Could not connect to the server |
| 4 | ERROR_TIMEOUT | Request timed out |
| 5 | ERROR_CONFIG | Configuration file error |
| 10 | ERROR_INVALID_ARGS | Invalid command arguments |
| 11 | ERROR_NOT_FOUND | Resource not found (group, job) |

**Note:** In submit command's default (lenient) mode, all errors result in exit code 0. Use `--strict` to enable error exit codes.

## Output Formatting

### Plain Mode (default when Rich not installed or `--no-color`)

```
$ statdash-cli health
System Health: ✅ HEALTHY
Total Jobs: 10
  Healthy: 8
  Unhealthy: 1
  In Progress: 1
```

### Rich Mode (when Rich is installed and TTY detected)

- Colored status indicators (green/red/yellow/blue)
- Formatted tables with borders
- Progress indicators for long operations
- Styled error messages

### JSON Mode (`--json`)

```json
{
  "status": "healthy",
  "total_jobs": 10,
  "healthy": 8,
  "unhealthy": 1,
  "in_progress": 1
}
```

---

## Implementation Phases

### Phase 1: Project Restructuring and Configuration

Refactor the existing CLI to support the new architecture and add configuration file support.

#### Project Setup

- [X] Create new module structure (`client.py`, `config.py`, `output.py`, `errors.py`)
- [X] Move `ApiClient` class to `client.py`
- [X] Add PyYAML dependency to `pyproject.toml`
- [X] Update package metadata in `pyproject.toml`

#### Configuration File Support

- [X] Implement config file discovery (check paths in order of precedence)
- [X] Implement YAML config file parser with schema validation
- [X] Add `--config` global option to specify config file path
- [X] Support `STATDASH_CONFIG` environment variable
- [X] Merge config sources: defaults < config file < env vars < CLI args
- [X] Add helpful error messages for invalid config files

#### Error Handling Foundation

- [X] Define exit code constants in `errors.py`
- [X] Create custom exception classes for different error types
- [X] Implement error-to-exit-code mapping
- [X] Add `--quiet` global option to suppress non-error output

---

### Phase 2: Enhanced Commands and Error Modes

Add group-level configuration command and implement the dual error handling modes.

#### Group Configuration Command

- [X] Add `get_group_config()` method to `ApiClient`
- [X] Add `update_group_config()` method to `ApiClient`
- [X] Implement `group-config` command with view mode
- [X] Implement `group-config` command with update mode
- [X] Add `--reset-progress-timeout` and `--reset-staleness-timeout` options
- [X] Add JSON output support for `group-config`

#### Submit Command Error Modes

- [X] Add `--strict` flag to submit command
- [X] Implement lenient mode (default): catch errors, log, exit 0
- [X] Implement strict mode: propagate errors with exit codes
- [X] Add `submit.strict` config file option
- [X] Add syslog support for error logging
- [X] Add `submit.syslog` and `submit.syslog_facility` config options
- [X] Ensure other commands (health, groups, jobs, config) always use strict error handling

#### API Client Improvements

- [X] Add configurable request timeout
- [X] Add `timeout` config file option
- [X] Improve error messages with more context
- [X] Add retry logic for transient failures (optional, configurable)

---

### Phase 3: Rich Output and Shell Completion

Enhance user experience with optional rich terminal output and shell completion.

#### Rich Terminal Output

- [X] Add Rich as optional dependency (`pip install statdash-cli[rich]`)
- [X] Create `output.py` module with output abstraction
- [X] Implement `PlainFormatter` class for basic output
- [X] Implement `RichFormatter` class for styled output
- [X] Auto-detect Rich availability and TTY status
- [X] Add `--no-color` global option
- [X] Add `color` config file option (true/false/auto)
- [X] Style health status with colors (green=healthy, red=error, yellow=progress)
- [X] Format group/job listings as styled tables
- [X] Style error messages with red highlighting

#### Shell Completion

- [X] Implement `completion` command
- [X] Generate Bash completion script
- [X] Generate Zsh completion script
- [X] Generate Fish completion script
- [X] Add dynamic completion for group names (queries API)
- [X] Add dynamic completion for job names within groups
- [X] Add completion for status values (success, error, progress)
- [X] Document completion installation in README

---

### Phase 4: Testing and Documentation

Comprehensive test coverage and documentation.

#### Unit Tests

- [X] Test `ApiClient` methods with mocked responses
- [X] Test config file parsing and merging
- [X] Test config file discovery logic
- [X] Test error handling and exit codes
- [X] Test output formatters (plain and rich)
- [X] Test submit command lenient vs strict modes
- [X] Test group-config command
- [X] Test shell completion generation

#### Integration Tests

- [X] Test CLI against running backend (pytest fixtures)
- [X] Test submit command end-to-end
- [X] Test health/groups/jobs queries
- [X] Test config and group-config commands
- [X] Test error scenarios (connection refused, timeouts, 404s)

#### Documentation

- [X] Update CLI README with full command reference
- [X] Document configuration file format and options
- [X] Add examples for common use cases:
  - [X] CI/CD pipeline integration
  - [X] Cron job status reporting
  - [X] Interactive terminal usage
  - [X] Script integration with `set -eu`
- [X] Document shell completion installation for each shell
- [X] Add troubleshooting section

---

### Phase 5: Polish and Release

Final polish and release preparation.

#### Code Quality

- [X] Run ruff format on all files
- [X] Run ruff check and fix all issues
- [X] Run mypy and fix all type errors
- [X] Review and update AIDEV-NOTE comments
- [X] Remove any dead code or unused imports

#### Release Preparation

- [X] Update version number in `pyproject.toml`
- [X] Verify all dependencies are correctly specified
- [X] Test installation from clean environment
- [X] Test with Python 3.10, 3.11, 3.12, 3.13
- [X] Create release notes

---

## Usage Examples

### CI/CD Pipeline (GitHub Actions)

```yaml
jobs:
  build:
    steps:
      - name: Report build start
        run: |
          statdash-cli submit -g ci-builds -j "${{ github.repository }}" \
            -s progress -m "Build started: ${{ github.sha }}"

      - name: Build
        run: make build

      - name: Report build success
        if: success()
        run: |
          statdash-cli submit -g ci-builds -j "${{ github.repository }}" \
            -s success -m "Build passed: ${{ github.sha }}"

      - name: Report build failure
        if: failure()
        run: |
          statdash-cli submit -g ci-builds -j "${{ github.repository }}" \
            -s error -m "Build failed: ${{ github.sha }}"
```

### Cron Job with Script Safety

```bash
#!/bin/bash
set -eu

# Submit commands won't cause script to exit on API errors
statdash-cli submit -g backups -j database -s progress -m "Starting backup"

# Do the actual backup
pg_dump mydb > /backups/mydb.sql

# Report success
statdash-cli submit -g backups -j database -s success -m "Backup completed"
```

### Cron Job with Strict Error Handling

```bash
#!/bin/bash
# No set -eu, handle errors manually

if ! statdash-cli submit --strict -g backups -j database -s progress; then
    echo "Warning: Could not report status to dashboard"
fi

pg_dump mydb > /backups/mydb.sql
backup_status=$?

if [ $backup_status -eq 0 ]; then
    statdash-cli submit -g backups -j database -s success
else
    statdash-cli submit -g backups -j database -s error -m "Backup failed with code $backup_status"
fi
```

### Interactive Terminal Session

```bash
# Check overall health with rich output
$ statdash-cli health

# List groups with status summary
$ statdash-cli groups

# Drill into a specific group
$ statdash-cli jobs nightly-builds

# Check group-specific timeout configuration
$ statdash-cli group-config nightly-builds

# Update group timeout (builds can take longer)
$ statdash-cli group-config nightly-builds --progress-timeout 30
```

### Configuration File Example

```yaml
# ~/.config/statdash/statdash.yaml
url: https://statdash.internal.example.com
color: auto
timeout: 30

submit:
  syslog: true
  syslog_facility: local0
  strict: false
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Lenient submit mode by default | Prevents status reporting from breaking scripts with `set -eu` |
| Strict mode for query commands | Users expect errors when querying non-existent resources |
| Optional Rich dependency | Works in minimal environments, enhanced where available |
| YAML config format | Human-readable, widely understood, good library support |
| Click for CLI framework | Already in use, mature, good completion support |
| Syslog support | Standard for daemon/cron job logging, doesn't pollute stdout/stderr |

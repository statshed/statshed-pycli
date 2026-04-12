# Changelog

All notable changes to Reporting In CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-18

### Added

- **Core Commands**
  - `submit` - Submit job status updates with support for success, error, and progress states
  - `health` - Check overall system health with detailed status counts
  - `groups` - List all groups with health summaries
  - `jobs` - List jobs within a specific group
  - `config` - View and update global timeout configuration
  - `group-config` - View and update group-specific timeout overrides
  - `completion` - Generate shell completion scripts for Bash, Zsh, and Fish

- **Configuration System**
  - YAML configuration file support with automatic discovery
  - Configuration file search order: CLI option > environment variable > ./reportingin-cli.yaml > ~/.config/reportingin/reportingin.yaml > /etc/reportingin/reportingin.yaml
  - Support for all settings: URL, timeout, retries, output format, color mode

- **Error Handling**
  - Dual-mode error handling for `submit` command:
    - Lenient mode (default): Errors logged but exit code 0, safe for scripts with `set -eu`
    - Strict mode (`--strict`): Errors produce non-zero exit codes
  - Syslog support for error logging in background jobs
  - Comprehensive exit codes for different error types

- **Output Formatting**
  - Plain text output with status indicators
  - Rich terminal output with colors and styled tables (optional dependency)
  - JSON output mode (`--json`) for machine consumption
  - Auto-detection of TTY and color support

- **API Client Features**
  - Configurable request timeout
  - Retry logic with jitter for transient failures
  - URL encoding for special characters in group/job names
  - Connection error and timeout handling

- **Shell Completion**
  - Dynamic completion for group names (queries API)
  - Dynamic completion for job names within groups
  - Static completion for status values
  - Support for Bash, Zsh, and Fish shells

- **Developer Experience**
  - Full type annotations with mypy strict mode
  - Comprehensive test suite (145+ tests)
  - Integration tests against real backend
  - Ruff linting and formatting

### Dependencies

- Required: click>=8.1.0, requests>=2.28.0, pyyaml>=6.0
- Optional: rich>=13.0.0 (for styled terminal output)
- Python: 3.10, 3.11, 3.12, 3.13

"""Configuration file handling for StatDash CLI.

AIDEV-NOTE: Configuration precedence (lowest to highest):
1. Built-in defaults
2. Config file (discovered or specified)
3. Environment variables
4. CLI arguments
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from statdash_cli.errors import ConfigError

# Default configuration values
DEFAULT_URL = "http://localhost:5000"
DEFAULT_OUTPUT_FORMAT = "table"
DEFAULT_COLOR = "auto"
DEFAULT_TIMEOUT = 10

# Configuration file search paths (in order of precedence)
CONFIG_SEARCH_PATHS = [
    Path("./statdash-cli.yaml"),
    Path.home() / ".config" / "statdash" / "config.yaml",
    Path("/etc/statdash/config.yaml"),
]


@dataclass
class SubmitConfig:
    """Submit command configuration."""

    syslog: bool = False
    syslog_facility: str = "user"
    strict: bool = False


@dataclass
class Config:
    """StatDash CLI configuration.

    AIDEV-NOTE: This dataclass holds all configuration values merged from
    various sources. The `from_sources()` classmethod handles the merging.
    """

    url: str = DEFAULT_URL
    output_format: str = DEFAULT_OUTPUT_FORMAT
    color: str = DEFAULT_COLOR
    timeout: int = DEFAULT_TIMEOUT
    submit: SubmitConfig = field(default_factory=SubmitConfig)
    config_path: Path | None = None

    @classmethod
    def from_sources(
        cls,
        config_path: str | None = None,
        cli_url: str | None = None,
        cli_no_color: bool = False,
        cli_json: bool = False,
    ) -> "Config":
        """Create configuration by merging all sources.

        Args:
            config_path: Explicit config file path (CLI arg or env var)
            cli_url: URL from CLI argument
            cli_no_color: No-color mode from CLI
            cli_json: JSON output mode from CLI

        Returns:
            Merged configuration
        """
        config = cls()

        # Load config file
        file_path = _find_config_file(config_path)
        if file_path:
            config = _load_config_file(file_path)
            config.config_path = file_path

        # Apply environment variables
        if env_url := os.environ.get("STATDASH_URL"):
            config.url = env_url

        # Apply CLI arguments (highest precedence)
        if cli_url:
            config.url = cli_url

        if cli_no_color:
            config.color = "never"

        if cli_json:
            config.output_format = "json"

        return config


def _find_config_file(explicit_path: str | None = None) -> Path | None:
    """Find the configuration file.

    Args:
        explicit_path: Path specified via --config or STATDASH_CONFIG

    Returns:
        Path to config file if found, None otherwise

    Raises:
        ConfigError: If explicit path doesn't exist
    """
    # Check explicit path first
    if explicit_path:
        path = Path(explicit_path)
        if not path.exists():
            raise ConfigError(f"Configuration file not found: {explicit_path}")
        return path

    # Check environment variable
    if env_config := os.environ.get("STATDASH_CONFIG"):
        path = Path(env_config)
        if not path.exists():
            raise ConfigError(f"Configuration file not found: {env_config}")
        return path

    # Search default paths
    for search_path in CONFIG_SEARCH_PATHS:
        if search_path.exists():
            return search_path

    return None


def _load_config_file(path: Path) -> "Config":
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML config file

    Returns:
        Parsed configuration

    Raises:
        ConfigError: If file cannot be parsed or contains invalid values
    """
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file {path}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Cannot read config file {path}: {e}") from e

    if data is None:
        return Config()

    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a YAML mapping, got {type(data).__name__}")

    return _parse_config(data, path)


def _parse_config(data: dict[str, Any], path: Path) -> "Config":
    """Parse configuration dictionary into Config object.

    Args:
        data: Configuration dictionary from YAML
        path: Path to config file (for error messages)

    Returns:
        Parsed configuration

    Raises:
        ConfigError: If configuration values are invalid
    """
    config = Config()

    # Parse URL
    if "url" in data:
        if not isinstance(data["url"], str):
            raise ConfigError(f"Config 'url' must be a string in {path}")
        config.url = data["url"]

    # Parse output_format
    if "output_format" in data:
        if data["output_format"] not in ("table", "json"):
            raise ConfigError(
                f"Config 'output_format' must be 'table' or 'json' in {path}, "
                f"got '{data['output_format']}'"
            )
        config.output_format = data["output_format"]

    # Parse color
    if "color" in data:
        color_val = data["color"]
        if isinstance(color_val, bool):
            config.color = "always" if color_val else "never"
        elif color_val in ("auto", "always", "never", True, False):
            if color_val is True:
                config.color = "always"
            elif color_val is False:
                config.color = "never"
            else:
                config.color = color_val
        else:
            raise ConfigError(
                f"Config 'color' must be true, false, or 'auto' in {path}, got '{color_val}'"
            )

    # Parse timeout
    if "timeout" in data:
        timeout = data["timeout"]
        if not isinstance(timeout, int) or timeout <= 0:
            raise ConfigError(f"Config 'timeout' must be a positive integer in {path}")
        config.timeout = timeout

    # Parse submit section
    if "submit" in data:
        submit_data = data["submit"]
        if not isinstance(submit_data, dict):
            raise ConfigError(f"Config 'submit' must be a mapping in {path}")

        if "syslog" in submit_data:
            if not isinstance(submit_data["syslog"], bool):
                raise ConfigError(f"Config 'submit.syslog' must be a boolean in {path}")
            config.submit.syslog = submit_data["syslog"]

        if "syslog_facility" in submit_data:
            if not isinstance(submit_data["syslog_facility"], str):
                raise ConfigError(f"Config 'submit.syslog_facility' must be a string in {path}")
            config.submit.syslog_facility = submit_data["syslog_facility"]

        if "strict" in submit_data:
            if not isinstance(submit_data["strict"], bool):
                raise ConfigError(f"Config 'submit.strict' must be a boolean in {path}")
            config.submit.strict = submit_data["strict"]

    return config

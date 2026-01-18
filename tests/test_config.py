"""Tests for configuration file handling."""

import os
import tempfile
from pathlib import Path

import pytest

from statdash_cli.config import (
    Config,
    ConfigError,
    SubmitConfig,
    _find_config_file,
    _load_config_file,
)


class TestConfigDefaults:
    """Test default configuration values."""

    def test_default_config(self) -> None:
        """Test that Config has sensible defaults."""
        config = Config()
        assert config.url == "http://localhost:5000"
        assert config.output_format == "table"
        assert config.color == "auto"
        assert config.timeout == 10
        assert config.submit.syslog is False
        assert config.submit.strict is False

    def test_submit_config_defaults(self) -> None:
        """Test SubmitConfig defaults."""
        submit = SubmitConfig()
        assert submit.syslog is False
        assert submit.syslog_facility == "user"
        assert submit.strict is False


class TestFindConfigFile:
    """Test config file discovery."""

    def test_explicit_path_exists(self, tmp_path: Path) -> None:
        """Test explicit config path that exists."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: http://example.com")

        result = _find_config_file(str(config_file))
        assert result == config_file

    def test_explicit_path_not_found(self) -> None:
        """Test explicit config path that doesn't exist."""
        with pytest.raises(ConfigError, match="Configuration file not found"):
            _find_config_file("/nonexistent/config.yaml")

    def test_env_var_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test STATDASH_CONFIG environment variable."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: http://example.com")

        monkeypatch.setenv("STATDASH_CONFIG", str(config_file))
        result = _find_config_file()
        assert result == config_file

    def test_env_var_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test STATDASH_CONFIG with nonexistent file."""
        monkeypatch.setenv("STATDASH_CONFIG", "/nonexistent/config.yaml")
        with pytest.raises(ConfigError, match="Configuration file not found"):
            _find_config_file()

    def test_no_config_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when no config file is found."""
        monkeypatch.delenv("STATDASH_CONFIG", raising=False)
        # Ensure we're not in a directory with a config file
        original_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                result = _find_config_file()
                assert result is None
        finally:
            os.chdir(original_cwd)


class TestLoadConfigFile:
    """Test config file loading and parsing."""

    def test_load_valid_config(self, tmp_path: Path) -> None:
        """Test loading a valid YAML config."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
url: http://example.com:8080
output_format: json
color: never
timeout: 30
submit:
  syslog: true
  syslog_facility: local0
  strict: true
""")
        config = _load_config_file(config_file)
        assert config.url == "http://example.com:8080"
        assert config.output_format == "json"
        assert config.color == "never"
        assert config.timeout == 30
        assert config.submit.syslog is True
        assert config.submit.syslog_facility == "local0"
        assert config.submit.strict is True

    def test_load_empty_config(self, tmp_path: Path) -> None:
        """Test loading an empty config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        config = _load_config_file(config_file)
        assert config.url == "http://localhost:5000"

    def test_load_partial_config(self, tmp_path: Path) -> None:
        """Test loading a config with only some fields."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: http://custom.example.com")

        config = _load_config_file(config_file)
        assert config.url == "http://custom.example.com"
        assert config.timeout == 10  # default

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        """Test loading invalid YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: [invalid yaml")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            _load_config_file(config_file)

    def test_non_mapping_yaml(self, tmp_path: Path) -> None:
        """Test YAML that's not a mapping."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- just\n- a\n- list")

        with pytest.raises(ConfigError, match="must contain a YAML mapping"):
            _load_config_file(config_file)

    def test_invalid_output_format(self, tmp_path: Path) -> None:
        """Test invalid output_format value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("output_format: invalid")

        with pytest.raises(ConfigError, match="must be 'table' or 'json'"):
            _load_config_file(config_file)

    def test_invalid_timeout(self, tmp_path: Path) -> None:
        """Test invalid timeout value."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("timeout: -5")

        with pytest.raises(ConfigError, match="must be a positive integer"):
            _load_config_file(config_file)

    def test_color_boolean_true(self, tmp_path: Path) -> None:
        """Test color: true."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("color: true")

        config = _load_config_file(config_file)
        assert config.color == "always"

    def test_color_boolean_false(self, tmp_path: Path) -> None:
        """Test color: false."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("color: false")

        config = _load_config_file(config_file)
        assert config.color == "never"


class TestConfigFromSources:
    """Test configuration merging from multiple sources."""

    def test_cli_url_overrides_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that CLI URL overrides config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: http://file.example.com")
        monkeypatch.setenv("STATDASH_CONFIG", str(config_file))

        config = Config.from_sources(cli_url="http://cli.example.com")
        assert config.url == "http://cli.example.com"

    def test_env_url_overrides_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that STATDASH_URL env var overrides config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("url: http://file.example.com")
        monkeypatch.setenv("STATDASH_CONFIG", str(config_file))
        monkeypatch.setenv("STATDASH_URL", "http://env.example.com")

        config = Config.from_sources()
        assert config.url == "http://env.example.com"

    def test_cli_url_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that CLI URL overrides environment variable."""
        monkeypatch.setenv("STATDASH_URL", "http://env.example.com")
        monkeypatch.delenv("STATDASH_CONFIG", raising=False)

        config = Config.from_sources(cli_url="http://cli.example.com")
        assert config.url == "http://cli.example.com"

    def test_no_color_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test --no-color flag sets color to never."""
        monkeypatch.delenv("STATDASH_CONFIG", raising=False)

        config = Config.from_sources(cli_no_color=True)
        assert config.color == "never"

    def test_json_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test --json flag sets output_format to json."""
        monkeypatch.delenv("STATDASH_CONFIG", raising=False)

        config = Config.from_sources(cli_json=True)
        assert config.output_format == "json"

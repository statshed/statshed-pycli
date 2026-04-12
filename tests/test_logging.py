"""Tests for logging utilities."""

from unittest import mock

from reportingin_cli.config import SubmitConfig
from reportingin_cli.logging import SYSLOG_FACILITIES, log_submit_error, log_to_syslog


class TestSyslogFacilities:
    """Test syslog facility mapping."""

    def test_user_facility(self) -> None:
        """Test user facility is mapped correctly."""
        import syslog

        assert SYSLOG_FACILITIES["user"] == syslog.LOG_USER

    def test_daemon_facility(self) -> None:
        """Test daemon facility is mapped correctly."""
        import syslog

        assert SYSLOG_FACILITIES["daemon"] == syslog.LOG_DAEMON

    def test_local_facilities(self) -> None:
        """Test local0-7 facilities are mapped correctly."""
        import syslog

        assert SYSLOG_FACILITIES["local0"] == syslog.LOG_LOCAL0
        assert SYSLOG_FACILITIES["local7"] == syslog.LOG_LOCAL7


class TestLogToSyslog:
    """Test log_to_syslog function."""

    @mock.patch("reportingin_cli.logging.syslog")
    def test_log_message(self, mock_syslog: mock.Mock) -> None:
        """Test logging a message to syslog."""
        log_to_syslog("Test message", "user")

        mock_syslog.openlog.assert_called_once()
        mock_syslog.syslog.assert_called_once()
        mock_syslog.closelog.assert_called_once()

        # Check the message was logged
        call_args = mock_syslog.syslog.call_args
        assert "Test message" in call_args[0]

    @mock.patch("reportingin_cli.logging.syslog")
    def test_log_with_facility(self, mock_syslog: mock.Mock) -> None:
        """Test logging with specific facility."""
        mock_syslog.LOG_LOCAL0 = 128
        log_to_syslog("Test message", "local0")

        # Check openlog was called with the right facility
        call_args = mock_syslog.openlog.call_args
        assert call_args[1]["facility"] == 128

    @mock.patch("reportingin_cli.logging.syslog")
    def test_log_unknown_facility_defaults_to_user(self, mock_syslog: mock.Mock) -> None:
        """Test that unknown facility defaults to LOG_USER."""
        mock_syslog.LOG_USER = 8
        log_to_syslog("Test message", "unknown_facility")

        call_args = mock_syslog.openlog.call_args
        assert call_args[1]["facility"] == 8


class TestLogSubmitError:
    """Test log_submit_error function."""

    @mock.patch("reportingin_cli.logging.log_to_syslog")
    def test_logs_when_syslog_enabled(self, mock_log: mock.Mock) -> None:
        """Test that errors are logged when syslog is enabled."""
        config = SubmitConfig(syslog=True, syslog_facility="local0")
        error = Exception("Test error")

        log_submit_error(error, config)

        mock_log.assert_called_once_with("Test error", "local0")

    @mock.patch("reportingin_cli.logging.log_to_syslog")
    def test_no_log_when_syslog_disabled(self, mock_log: mock.Mock) -> None:
        """Test that errors are not logged when syslog is disabled."""
        config = SubmitConfig(syslog=False)
        error = Exception("Test error")

        log_submit_error(error, config)

        mock_log.assert_not_called()

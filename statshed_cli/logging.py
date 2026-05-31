"""Logging utilities for StatShed CLI.

AIDEV-NOTE: This module provides syslog integration for error logging.
Syslog is used when submit.syslog is enabled in config, primarily for
daemon/cron job scenarios where stderr may not be monitored.
"""

import syslog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from statshed_cli.config import SubmitConfig

# Mapping of facility names to syslog constants
# AIDEV-NOTE: These are standard syslog facilities. Most users will use "user"
# or "local0"-"local7" for custom applications.
SYSLOG_FACILITIES: dict[str, int] = {
    "user": syslog.LOG_USER,
    "daemon": syslog.LOG_DAEMON,
    "local0": syslog.LOG_LOCAL0,
    "local1": syslog.LOG_LOCAL1,
    "local2": syslog.LOG_LOCAL2,
    "local3": syslog.LOG_LOCAL3,
    "local4": syslog.LOG_LOCAL4,
    "local5": syslog.LOG_LOCAL5,
    "local6": syslog.LOG_LOCAL6,
    "local7": syslog.LOG_LOCAL7,
}


def log_to_syslog(message: str, facility: str = "user") -> None:
    """Log a message to syslog.

    Args:
        message: The message to log
        facility: Syslog facility name (user, daemon, local0-7)
    """
    facility_code = SYSLOG_FACILITIES.get(facility, syslog.LOG_USER)

    # Open syslog with the program name
    syslog.openlog(ident="statshed", logoption=syslog.LOG_PID, facility=facility_code)
    try:
        syslog.syslog(syslog.LOG_WARNING, message)
    finally:
        syslog.closelog()


def log_submit_error(error: Exception, submit_config: "SubmitConfig") -> None:
    """Log a submit command error.

    If syslog is enabled in config, logs to syslog. Otherwise does nothing
    (caller handles stderr output).

    Args:
        error: The error that occurred
        submit_config: Submit command configuration
    """
    if submit_config.syslog:
        log_to_syslog(str(error), submit_config.syslog_facility)

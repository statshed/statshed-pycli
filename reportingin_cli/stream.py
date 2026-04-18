"""Stream command core: line filtering and debounced submission.

AIDEV-NOTE: The IO loop lives in main.py (uses ``select`` on stdin). This module
holds the pure state-machine so it can be unit tested without real IO or a real
clock. Inject ``time_fn`` to control time in tests.

Behavior:
- Every accepted line is submitted as a "progress" status message.
- Leading/trailing whitespace and ANSI escape sequences are stripped.
- ``--regex`` patterns are an include filter (at least one must ``re.search``
  the cleaned line). ``--ignore`` patterns are an exclude filter applied after.
- The first accepted line is sent immediately. Subsequent lines within the
  ``min_time`` window are stored as a "pending" message using last-wins
  semantics; when the window expires the pending message is flushed.
- On EOF any pending message is flushed unconditionally.
"""

import re
from collections.abc import Callable
from time import monotonic

# AIDEV-NOTE: Matches the ECMA-48 escape sequences we care about for log scrubbing
# (CSI "ESC [ ... final-byte" plus the short single-character escapes). Good
# enough for colored/formatted output from typical logging libraries.
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from ``text``."""
    return ANSI_ESCAPE_RE.sub("", text)


def clean_line(raw: str) -> str:
    """Strip ANSI codes and surrounding whitespace from a raw input line."""
    return strip_ansi(raw).strip()


class StreamProcessor:
    """Debounced, filtered status-message submitter.

    AIDEV-NOTE: This class is intentionally IO-free. ``send_fn`` is called to
    submit a message; the caller is responsible for handling errors and for
    driving ``time_until_next_flush``/``flush_if_due`` based on real time.
    """

    def __init__(
        self,
        min_time: float,
        regex_patterns: list[re.Pattern[str]],
        ignore_patterns: list[re.Pattern[str]],
        send_fn: Callable[[str], None],
        time_fn: Callable[[], float] = monotonic,
    ) -> None:
        self.min_time = min_time
        self.regex_patterns = regex_patterns
        self.ignore_patterns = ignore_patterns
        self.send_fn = send_fn
        self.time_fn = time_fn
        self._last_send_time: float | None = None
        self._pending_message: str | None = None

    def process_line(self, raw_line: str) -> None:
        """Process a single raw input line; may call ``send_fn``."""
        cleaned = clean_line(raw_line)
        if not cleaned:
            return

        if self.regex_patterns and not any(p.search(cleaned) for p in self.regex_patterns):
            return
        if any(p.search(cleaned) for p in self.ignore_patterns):
            return

        now = self.time_fn()
        if self._last_send_time is None or (now - self._last_send_time) >= self.min_time:
            self._send(cleaned, now)
        else:
            # AIDEV-NOTE: Last-wins debounce — newer messages overwrite older
            # ones within the window. The pending message is flushed by either
            # ``flush_if_due`` (on timer) or ``flush_pending`` (on EOF).
            self._pending_message = cleaned

    def time_until_next_flush(self) -> float | None:
        """Seconds until a pending message is due to flush, or ``None`` if idle."""
        if self._pending_message is None or self._last_send_time is None:
            return None
        elapsed = self.time_fn() - self._last_send_time
        return max(0.0, self.min_time - elapsed)

    def flush_if_due(self) -> None:
        """Flush the pending message if the ``min_time`` window has elapsed."""
        if self._pending_message is None:
            return
        now = self.time_fn()
        if self._last_send_time is None or (now - self._last_send_time) >= self.min_time:
            self._send(self._pending_message, now)

    def flush_pending(self) -> None:
        """Unconditionally flush any pending message (used on EOF)."""
        if self._pending_message is not None:
            self._send(self._pending_message, self.time_fn())

    def _send(self, message: str, now: float) -> None:
        self.send_fn(message)
        self._last_send_time = now
        self._pending_message = None


def compile_patterns(patterns: tuple[str, ...], ignore_case: bool) -> list[re.Pattern[str]]:
    """Compile a tuple of user-supplied regex strings.

    Raises:
        re.error: If any pattern is invalid.
    """
    flags = re.IGNORECASE if ignore_case else 0
    return [re.compile(p, flags) for p in patterns]

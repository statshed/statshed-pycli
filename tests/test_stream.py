"""Tests for the stream processor state machine.

AIDEV-NOTE: These tests exercise ``StreamProcessor`` directly with a manual
clock so timing behavior is deterministic. End-to-end CLI behavior (stdin
piping, select loop, error propagation) is covered in ``test_commands.py``.
"""

import re

import pytest

from statshed_cli.stream import (
    ANSI_ESCAPE_RE,
    StreamProcessor,
    clean_line,
    compile_patterns,
    strip_ansi,
)


class FakeClock:
    """Deterministic replacement for ``time.monotonic``."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class Collector:
    """Records messages passed to ``send_fn``."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)


def make_processor(
    sent: Collector,
    clock: FakeClock,
    *,
    min_time: float = 60.0,
    regex_patterns: list[re.Pattern[str]] | None = None,
    ignore_patterns: list[re.Pattern[str]] | None = None,
) -> StreamProcessor:
    return StreamProcessor(
        min_time=min_time,
        regex_patterns=regex_patterns or [],
        ignore_patterns=ignore_patterns or [],
        send_fn=sent,
        time_fn=clock,
    )


class TestAnsiStripping:
    def test_strips_color_codes(self) -> None:
        assert strip_ansi("\x1b[31mhello\x1b[0m") == "hello"

    def test_strips_cursor_movement(self) -> None:
        assert strip_ansi("\x1b[2K\x1b[1Areset") == "reset"

    def test_leaves_plain_text_untouched(self) -> None:
        assert strip_ansi("plain text") == "plain text"

    def test_clean_line_strips_whitespace_and_ansi(self) -> None:
        assert clean_line("  \x1b[32mok\x1b[0m  \n") == "ok"

    def test_regex_matches_short_escapes(self) -> None:
        # Single-character ESC sequences like ESC M (reverse index).
        assert ANSI_ESCAPE_RE.sub("", "a\x1bMb") == "ab"


class TestFirstMessageImmediate:
    def test_first_line_sent_immediately(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock)

        p.process_line("first\n")

        assert sent.messages == ["first"]

    def test_empty_line_does_not_count_as_first(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock)

        p.process_line("   \n")
        p.process_line("\x1b[31m\x1b[0m\n")  # pure ANSI, strips to empty
        p.process_line("real\n")

        assert sent.messages == ["real"]


class TestDebounce:
    def test_second_line_within_window_is_deferred(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("one\n")
        clock.advance(5)
        p.process_line("two\n")

        assert sent.messages == ["one"]

    def test_last_line_within_window_wins(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("one\n")
        clock.advance(5)
        p.process_line("two\n")
        clock.advance(5)
        p.process_line("three\n")
        clock.advance(5)
        p.process_line("four\n")

        clock.advance(60)
        p.flush_if_due()

        assert sent.messages == ["one", "four"]

    def test_line_after_window_is_sent_immediately(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("one\n")
        clock.advance(61)
        p.process_line("two\n")

        assert sent.messages == ["one", "two"]

    def test_line_after_window_supersedes_pending(self) -> None:
        """A post-window line sends itself, not an older pending message."""
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("one\n")
        clock.advance(5)
        p.process_line("pending\n")  # becomes pending
        clock.advance(60)
        p.process_line("fresh\n")  # window passed → sent directly

        assert sent.messages == ["one", "fresh"]
        # And no leftover pending to flush.
        p.flush_pending()
        assert sent.messages == ["one", "fresh"]

    def test_flush_if_due_noop_before_window(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("one\n")
        clock.advance(5)
        p.process_line("two\n")
        clock.advance(30)  # still inside the window
        p.flush_if_due()

        assert sent.messages == ["one"]

    def test_min_time_zero_sends_every_line(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=0.0)

        p.process_line("a\n")
        p.process_line("b\n")
        p.process_line("c\n")

        assert sent.messages == ["a", "b", "c"]


class TestTimeUntilNextFlush:
    def test_none_when_idle(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock)
        assert p.time_until_next_flush() is None

    def test_none_after_send_with_no_pending(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock)
        p.process_line("first\n")
        assert p.time_until_next_flush() is None

    def test_returns_remaining_seconds_with_pending(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("first\n")
        clock.advance(10)
        p.process_line("pending\n")

        # 60s window - 10s elapsed = 50s remaining.
        assert p.time_until_next_flush() == pytest.approx(50.0)

    def test_returns_zero_when_window_already_elapsed(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("first\n")
        clock.advance(10)
        p.process_line("pending\n")
        clock.advance(100)

        assert p.time_until_next_flush() == 0.0


class TestFlushPending:
    def test_flush_pending_sends_deferred_message(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, min_time=60.0)

        p.process_line("one\n")
        clock.advance(5)
        p.process_line("two\n")
        p.flush_pending()

        assert sent.messages == ["one", "two"]

    def test_flush_pending_noop_when_nothing_pending(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock)

        p.flush_pending()
        p.process_line("one\n")
        p.flush_pending()

        assert sent.messages == ["one"]


class TestRegexFilters:
    def test_include_regex_skips_non_matching(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(
            sent,
            clock,
            regex_patterns=[re.compile(r"ERROR")],
        )

        p.process_line("INFO starting\n")
        p.process_line("ERROR boom\n")

        assert sent.messages == ["ERROR boom"]

    def test_include_regex_uses_search_not_fullmatch(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(
            sent,
            clock,
            regex_patterns=[re.compile(r"boom")],
        )

        p.process_line("2026-04-17 12:00 boom happened\n")

        assert sent.messages == ["2026-04-17 12:00 boom happened"]

    def test_multiple_include_regexes_use_OR(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(
            sent,
            clock,
            regex_patterns=[re.compile(r"ERROR"), re.compile(r"WARN")],
        )

        p.process_line("INFO hi\n")
        p.process_line("ERROR bad\n")
        clock.advance(100)
        p.process_line("WARN worse\n")

        assert sent.messages == ["ERROR bad", "WARN worse"]

    def test_ignore_regex_drops_matching(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(
            sent,
            clock,
            ignore_patterns=[re.compile(r"heartbeat")],
        )

        p.process_line("heartbeat 1\n")
        p.process_line("real work\n")

        assert sent.messages == ["real work"]

    def test_include_and_ignore_combined(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(
            sent,
            clock,
            regex_patterns=[re.compile(r"job")],
            ignore_patterns=[re.compile(r"heartbeat")],
        )

        p.process_line("random noise\n")  # no include match
        p.process_line("job started\n")  # included
        p.process_line("job heartbeat\n")  # included then excluded

        assert sent.messages == ["job started"]

    def test_ignore_case_flag(self) -> None:
        patterns = compile_patterns(("error",), ignore_case=True)
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, regex_patterns=patterns)

        p.process_line("ERROR loud\n")
        p.process_line("Error quiet\n")

        # Both matched the case-insensitive include filter. First sent
        # immediately; second held as pending.
        assert sent.messages == ["ERROR loud"]
        p.flush_pending()
        assert sent.messages == ["ERROR loud", "Error quiet"]

    def test_case_sensitive_by_default(self) -> None:
        patterns = compile_patterns(("error",), ignore_case=False)
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock, regex_patterns=patterns)

        p.process_line("ERROR loud\n")
        p.process_line("error quiet\n")

        assert sent.messages == ["error quiet"]


class TestStripping:
    def test_strips_whitespace_before_submit(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock)

        p.process_line("   hello world  \n")

        assert sent.messages == ["hello world"]

    def test_strips_ansi_before_submit(self) -> None:
        sent = Collector()
        clock = FakeClock()
        p = make_processor(sent, clock)

        p.process_line("\x1b[32mdone\x1b[0m\n")

        assert sent.messages == ["done"]


class TestCompilePatterns:
    def test_empty_input_returns_empty_list(self) -> None:
        assert compile_patterns((), ignore_case=False) == []

    def test_invalid_regex_raises(self) -> None:
        with pytest.raises(re.error):
            compile_patterns(("[unclosed",), ignore_case=False)

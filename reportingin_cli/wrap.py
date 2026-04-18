"""Wrap command core: subprocess lifecycle and IO multiplexing.

AIDEV-NOTE: The Click command itself lives in ``main.py``. This module owns
the subprocess plumbing — spawning the child, forwarding stdin, multiplexing
stdout/stderr through a ``StreamProcessor``, and propagating signals.

Behavior summary:
- Stdin from the wrapper is piped to the child's stdin; EOF on our stdin
  closes the child's stdin.
- Child stdout and stderr are read concurrently; each complete line is fed
  into the ``StreamProcessor`` and (unless ``swallow=True``) echoed through
  to the wrapper's stdout/stderr respectively.
- If ``log_file`` is given, raw output bytes (both streams, interleaved in
  arrival order) are tee'd into it for later attachment to a final status.
- SIGINT and SIGTERM received by the wrapper are forwarded to the child;
  the wrapper then waits for the child to exit.
"""

import contextlib
import os
import selectors
import signal
import subprocess
import sys
from types import FrameType
from typing import IO

from reportingin_cli.stream import StreamProcessor


# AIDEV-NOTE: Shell convention for signal-terminated processes: exit code
# 128 + signal number. We convert Python's negative Popen.returncode for
# signals into this form so the wrapper's exit code matches what a shell
# would report if it had invoked the command directly.
def _normalize_exit_code(returncode: int) -> int:
    if returncode < 0:
        return 128 + abs(returncode)
    return returncode


def run_wrapped(
    argv: list[str],
    processor: StreamProcessor,
    *,
    swallow: bool = False,
    log_file: IO[bytes] | None = None,
) -> tuple[int, str | None]:
    """Spawn ``argv`` and drive IO until it exits.

    Returns a tuple of (shell-style exit code, last submitted message).
    The last message is whatever the ``StreamProcessor`` most recently
    accepted — useful as the message body of a final status update.

    Raises:
        FileNotFoundError: If ``argv[0]`` is not executable.
    """
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    # AIDEV-NOTE: Wrap send_fn to capture the last message. We can't peek
    # inside StreamProcessor (no public accessor) and the debounce means the
    # last *processed* line isn't always the last *sent* message — we want
    # the sent one so the final status reflects what the user actually saw.
    original_send = processor.send_fn
    last_message: list[str | None] = [None]

    def capturing_send(message: str) -> None:
        last_message[0] = message
        original_send(message)

    processor.send_fn = capturing_send

    previous_handlers: dict[signal.Signals, object] = {}

    def forward(signum: int, _frame: FrameType | None) -> None:
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.send_signal(signum)

    for sig in (signal.SIGINT, signal.SIGTERM):
        # Not on the main thread → signal.signal raises ValueError; skip.
        with contextlib.suppress(ValueError, OSError):
            previous_handlers[sig] = signal.signal(sig, forward)

    try:
        _drive_io(proc, processor, swallow=swallow, log_file=log_file)
        processor.flush_pending()
        returncode = proc.wait()
    finally:
        for sig, handler in previous_handlers.items():
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, handler)  # type: ignore[arg-type]
        processor.send_fn = original_send
        # Ensure pipes are closed so the child doesn't hang on a half-open fd.
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            if stream is not None:
                with contextlib.suppress(OSError):
                    stream.close()

    return _normalize_exit_code(returncode), last_message[0]


def _drive_io(
    proc: subprocess.Popen[bytes],
    processor: StreamProcessor,
    *,
    swallow: bool,
    log_file: IO[bytes] | None,
) -> None:
    """Multiplex stdin/stdout/stderr until the child closes both output pipes."""
    sel = selectors.DefaultSelector()

    assert proc.stdout is not None
    assert proc.stderr is not None
    sel.register(proc.stdout, selectors.EVENT_READ, data="stdout")
    sel.register(proc.stderr, selectors.EVENT_READ, data="stderr")

    # Stdin forwarding is best-effort. If our stdin isn't a real fd (e.g.
    # Click's in-memory CliRunner stream), skip it; the child just gets EOF.
    stdin_fd = _try_fileno(sys.stdin)
    stdin_closed = False
    if stdin_fd is None and proc.stdin is not None:
        with contextlib.suppress(OSError):
            proc.stdin.close()
        stdin_closed = True
    elif stdin_fd is not None:
        sel.register(stdin_fd, selectors.EVENT_READ, data="stdin")

    buffers: dict[str, bytes] = {"stdout": b"", "stderr": b""}

    outputs_open = 2
    while outputs_open > 0:
        timeout = processor.time_until_next_flush()
        events = sel.select(timeout)
        if not events:
            processor.flush_if_due()
            continue

        for key, _mask in events:
            stream_name: str = key.data

            if stream_name == "stdin":
                # AIDEV-NOTE: Forward wrapper stdin -> child stdin. On EOF
                # from our stdin, close the child's stdin so commands that
                # read to EOF (cat, sort, etc.) can finish.
                try:
                    chunk = os.read(stdin_fd, 4096)  # type: ignore[arg-type]
                except OSError:
                    chunk = b""
                if not chunk:
                    sel.unregister(stdin_fd)  # type: ignore[arg-type]
                    if not stdin_closed and proc.stdin is not None:
                        with contextlib.suppress(OSError):
                            proc.stdin.close()
                        stdin_closed = True
                else:
                    try:
                        assert proc.stdin is not None
                        proc.stdin.write(chunk)
                        proc.stdin.flush()
                    except (OSError, BrokenPipeError):
                        sel.unregister(stdin_fd)  # type: ignore[arg-type]
                        stdin_closed = True
                continue

            # stdout / stderr from child
            try:
                chunk = os.read(key.fd, 4096)
            except OSError:
                chunk = b""

            if not chunk:
                sel.unregister(key.fileobj)
                # Flush a trailing unterminated line, if any.
                leftover = buffers[stream_name]
                if leftover:
                    _emit_line(
                        leftover.decode("utf-8", errors="replace"),
                        stream_name,
                        processor,
                        swallow,
                    )
                    buffers[stream_name] = b""
                outputs_open -= 1
                continue

            if log_file is not None:
                log_file.write(chunk)

            buf = buffers[stream_name] + chunk
            while (nl := buf.find(b"\n")) != -1:
                line_bytes = buf[: nl + 1]
                buf = buf[nl + 1 :]
                _emit_line(
                    line_bytes.decode("utf-8", errors="replace"),
                    stream_name,
                    processor,
                    swallow,
                )
            buffers[stream_name] = buf


def _emit_line(
    line: str,
    stream_name: str,
    processor: StreamProcessor,
    swallow: bool,
) -> None:
    if not swallow:
        out = sys.stdout if stream_name == "stdout" else sys.stderr
        out.write(line)
        out.flush()
    processor.process_line(line)


def _try_fileno(stream: object) -> int | None:
    """Return ``stream.fileno()`` if it points at a real OS fd, else ``None``."""
    try:
        fd: int = stream.fileno()  # type: ignore[attr-defined]
    except (AttributeError, OSError, ValueError):
        return None
    try:
        os.fstat(fd)
    except OSError:
        return None
    return fd

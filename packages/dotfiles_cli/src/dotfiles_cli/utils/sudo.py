"""Sudo password validation and ticket keep-alive utilities."""

from __future__ import annotations

import subprocess
import threading

# Comfortably under macOS/sudo's default 5-minute (300s) timestamp_timeout,
# so the cached ticket never lapses between refreshes.
_KEEPALIVE_INTERVAL_SECONDS = 50


def validate_sudo_password(password: str) -> bool:
    """Validate that the given password is correct for sudo.

    Uses `sudo -S -v` to validate the password without running any command.
    The -S flag reads password from stdin, -v updates the cached credentials.

    Args:
        password: The sudo password to validate

    Returns:
        True if the password is valid, False otherwise
    """
    try:
        result = subprocess.run(
            ["sudo", "-S", "-v"],
            input=password + "\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


class SudoKeepAlive:
    """Keeps the OS sudo ticket warm for the duration of a long-running deploy.

    `validate_sudo_password` already primes the cached ticket via `sudo -S -v`,
    but that ticket expires (default 5 min on macOS) if the deploy outlives it —
    at which point sudo prompts interactively again, mid-run. This refreshes the
    ticket with plain `sudo -n -v` (no password needed, just extends the cache)
    on a background thread so callers never need to hold the password past the
    initial validation.
    """

    def __init__(self, interval: int = _KEEPALIVE_INTERVAL_SECONDS) -> None:
        self._interval: int = interval
        self._stop_event: threading.Event = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            _ = subprocess.run(
                ["sudo", "-n", "-v"],
                capture_output=True,
                check=False,
            )

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

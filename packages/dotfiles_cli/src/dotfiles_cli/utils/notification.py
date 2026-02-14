"""macOS notification utilities for the dotfiles CLI."""

from __future__ import annotations

import os
import shutil
import subprocess


def send_notification(title: str, message: str, group: str = "dotfiles-cli") -> None:
    """Send a macOS notification using terminal-notifier or osascript fallback.

    Runs in background to avoid blocking. Silently fails if neither tool is available.
    Skips notifications in CI/test environments.

    Args:
        title: Notification title
        message: Notification message body
        group: Notification group identifier (for terminal-notifier)
    """
    # Skip notifications in CI/test environments
    if os.environ.get("CI") or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    terminal_notifier = shutil.which("terminal-notifier")
    if terminal_notifier:
        # Pipe message to avoid escaping issues
        # https://github.com/julienXX/terminal-notifier/issues/134
        try:
            proc = subprocess.Popen(
                [terminal_notifier, "-title", title, "-group", group],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Write message and close stdin without waiting for process
            if proc.stdin:
                proc.stdin.write(message.encode())
                proc.stdin.close()
        except (subprocess.SubprocessError, OSError):
            pass
        return

    osascript = shutil.which("osascript")
    if osascript:
        escaped_title = title.replace('"', '\\"')
        escaped_message = message.replace('"', '\\"')
        try:
            subprocess.Popen(
                [
                    osascript,
                    "-e",
                    f'display notification "{escaped_message}" with title "{escaped_title}"',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except (subprocess.SubprocessError, OSError):
            pass

"""Change the login shell — prefer fish, fall back to zsh.

Mirrors the logic of ``roles/chsh/tasks/main.yml``.

Shell paths are discovered at build time (where pyinfra assembles the
operation list), not at runtime. The operations themselves run under sudo
because both ``/etc/shells`` and ``chsh`` require elevated privileges.

Idempotency: each ``chsh`` is guarded by reading the user's current shell via
``dscl`` so the operation only reports changed when it actually changes the
shell. Without this guard ``chsh`` would always be reported as changed.
"""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path
from typing import Any

from pyinfra.operations import server


def deploy(merged: dict[str, Any]) -> None:
    """Set the login shell to fish if available, otherwise zsh."""
    # No config needed from `merged`; signature kept uniform with other deploys.
    _ = merged

    user = os.environ.get("USER") or os.getlogin()

    fish_path = _discover_fish()
    zsh_path = shutil.which("zsh") or "/bin/zsh"

    if fish_path:
        _ensure_in_etc_shells(fish_path)
        _change_shell(user, fish_path)
    else:
        # Fallback: ensure at least zsh is the login shell.
        _change_shell(user, zsh_path)


def _discover_fish() -> str | None:
    """Locate the fish binary, preferring well-known install locations."""
    for candidate in ("/opt/homebrew/bin/fish", "/usr/local/bin/fish", "/usr/bin/fish"):
        if Path(candidate).exists():
            return candidate
    return shutil.which("fish")


def _ensure_in_etc_shells(shell_path: str) -> None:
    """Append ``shell_path`` to /etc/shells if it is not already listed."""
    quoted = shlex.quote(shell_path)
    server.shell(
        name=f"Ensure {shell_path} is in /etc/shells",
        commands=[
            f"grep -qxF {quoted} /etc/shells || echo {quoted} >> /etc/shells",
        ],
        _sudo=True,
    )


def _change_shell(user: str, shell_path: str) -> None:
    """Change ``user``'s login shell to ``shell_path`` (idempotent)."""
    quoted_user = shlex.quote(user)
    quoted_shell = shlex.quote(shell_path)
    server.shell(
        name=f"Change shell for {user} to {shell_path}",
        commands=[
            f"dscl . -read /Users/{quoted_user} UserShell"
            f" | grep -qF {quoted_shell}"
            f" || chsh -s {quoted_shell} {quoted_user}",
        ],
        _sudo=True,
    )

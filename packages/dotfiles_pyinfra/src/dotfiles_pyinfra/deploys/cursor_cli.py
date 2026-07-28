"""Install or upgrade the Cursor CLI (``agent``).

Mirrors the logic of ``roles/cursor_cli/tasks/main.yml``.

Whether ``agent`` is already on PATH is determined at build time. If it is not
installed we run the upstream install script; if it is, we run ``agent upgrade``.
The upgrade op is always emitted and will always be reported as changed — that
is acceptable and matches the behaviour described in the task spec.
"""

from __future__ import annotations

import shutil
from typing import Any

from pyinfra.operations import server


def deploy(merged: dict[str, Any]) -> None:
    """Install Cursor CLI when missing, otherwise upgrade it."""
    if not merged.get("install_cursor_cli", False):
        return

    agent_installed = shutil.which("agent") is not None

    if not agent_installed:
        server.shell(
            name="Install Cursor CLI",
            commands=["curl https://cursor.com/install -fsS | bash"],
        )
    else:
        server.shell(
            name="Upgrade Cursor CLI",
            commands=["agent upgrade || true"],
        )

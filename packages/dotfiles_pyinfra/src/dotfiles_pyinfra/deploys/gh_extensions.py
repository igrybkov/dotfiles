"""gh_extensions deploy — GitHub CLI extensions.

Mirrors the logic of ``roles/gh_extensions/tasks/main.yml``.

States:
  * ``absent``  — remove if installed
  * ``present`` — install if not installed (default)
  * ``latest``  — install if missing, else upgrade to the newest version

Idempotency is inline in the shell (``gh extension list 2>/dev/null | grep ...``)
so it degrades gracefully when ``gh`` was only just installed by brew earlier in
the same run — we do NOT short-circuit the whole role on a ``which gh`` guard the
way the Ansible role did, because that would skip installs on a fresh machine.
"""

from __future__ import annotations

import shlex
from typing import Any

from pyinfra.operations import server


def deploy(merged: dict[str, Any]) -> None:
    """Install/remove/upgrade gh CLI extensions for the merged profile data."""
    extensions: list[dict[str, Any]] = merged.get("gh_extensions", [])
    if not extensions:
        return

    for ext in extensions:
        name = ext["name"]
        state = ext.get("state", "present")
        # `gh extension upgrade` takes just the repo part (after the slash).
        short = name.split("/")[-1]
        quoted_name = shlex.quote(name)
        # Match the owner/repo on its own field in `gh extension list` output.
        quoted_short = shlex.quote(short)

        if state == "absent":
            server.shell(
                name=f"Remove gh extension {name}",
                commands=[
                    f"(gh extension list 2>/dev/null || echo '')"
                    f" | grep -q {quoted_short}"
                    f" && gh extension remove {quoted_short} || true"
                ],
            )
        elif state == "latest":
            # Upgrade when present, install when missing — single op.
            server.shell(
                name=f"Install or upgrade gh extension {name} (latest)",
                commands=[
                    f"(gh extension list 2>/dev/null || echo '')"
                    f" | grep -q {quoted_short}"
                    f" && gh extension upgrade {quoted_short}"
                    f" || gh extension install {quoted_name}"
                ],
            )
        else:  # present
            server.shell(
                name=f"Install gh extension {name}",
                commands=[
                    f"(gh extension list 2>/dev/null || echo '')"
                    f" | grep -q {quoted_short}"
                    f" || gh extension install {quoted_name}"
                ],
            )

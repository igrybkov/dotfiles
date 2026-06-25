"""composer deploy — global Composer (PHP) packages.

Mirrors the logic of ``roles/composer/tasks/main.yml``.

Steps (same as the Ansible role):
  1. Skip entirely if no composer packages are configured
  2. Skip with a log message if ``composer`` is not on PATH
  3. ``composer global require`` present packages; ``composer global remove``
     absent ones. Each is idempotency-guarded via ``composer global show`` so
     re-runs are no-ops.

Composer has no native pyinfra operation, so all work goes through
``server.shell``. ``composer`` is resolved at deploy-build time via
``shutil.which`` (it is a pre-existing tool).
"""

from __future__ import annotations

import shlex
import shutil
from typing import Any

from pyinfra import logger
from pyinfra.operations import server


def deploy(merged: dict[str, Any]) -> None:
    """Install/remove global composer packages for the given merged profile data."""
    packages: list[dict[str, Any]] = merged.get("composer_packages", [])
    if not packages:
        return

    if not shutil.which("composer"):
        names = ", ".join(p["name"] for p in packages)
        logger.warning(
            f"composer not found — add 'composer' to brew_packages. Skipping composer packages: {names}"
        )
        return

    for pkg in packages:
        name = pkg["name"]
        quoted = shlex.quote(name)
        if pkg.get("state", "present") == "absent":
            server.shell(
                name=f"Remove composer package {name}",
                commands=[
                    f"composer global show {quoted} >/dev/null 2>&1"
                    f" && composer global remove {quoted} || true"
                ],
            )
        else:
            server.shell(
                name=f"Require composer package {name}",
                commands=[
                    f"composer global show {quoted} >/dev/null 2>&1"
                    f" || composer global require {quoted}"
                ],
            )

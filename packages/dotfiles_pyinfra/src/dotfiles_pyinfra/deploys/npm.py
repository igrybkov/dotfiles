"""npm deploy — global npm packages.

Mirrors the logic of ``roles/npm/tasks/main.yml``.

Steps (same as the Ansible role):
  1. Skip entirely if no npm packages are configured
  2. Skip with a log message if ``npm`` is not on PATH
  3. Install present packages globally; uninstall absent ones
"""

from __future__ import annotations

from typing import Any

from pyinfra import host, logger
from pyinfra.facts.server import Which
from pyinfra.operations import npm


def deploy(merged: dict[str, Any]) -> None:
    """Install/remove global npm packages for the given merged profile data."""
    packages: list[dict[str, Any]] = merged.get("npm_packages", [])
    if not packages:
        return

    if not host.get_fact(Which, command="npm"):
        names = ", ".join(p["name"] for p in packages)
        logger.warning(
            "npm not found in PATH — add 'node' to brew_packages. "
            f"Skipping npm packages: {names}"
        )
        return

    present = [p["name"] for p in packages if p.get("state", "present") != "absent"]
    absent = [p["name"] for p in packages if p.get("state") == "absent"]

    # pyinfra's npm.packages installs globally when ``directory`` is unset
    # (the default), matching the Ansible role's ``global: true``.
    if present:
        npm.packages(
            name=f"Install {len(present)} npm package(s)",
            packages=present,
            present=True,
        )
    if absent:
        npm.packages(
            name=f"Uninstall {len(absent)} npm package(s)",
            packages=absent,
            present=False,
        )

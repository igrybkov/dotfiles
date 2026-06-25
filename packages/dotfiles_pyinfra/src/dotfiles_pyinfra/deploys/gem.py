"""gem deploy — Ruby gems.

Mirrors the logic of ``roles/gem/tasks/main.yml``.

Steps (same as the Ansible role):
  1. Skip entirely if no gem packages are configured
  2. Skip with a log message if ``gem`` is not on PATH
  3. Install present packages; uninstall absent ones. Versioned installs are
     handled via shell since ``gem.packages`` only takes plain names.
"""

from __future__ import annotations

import shlex
from typing import Any

from pyinfra import host, logger
from pyinfra.facts.server import Which
from pyinfra.operations import gem, server


def deploy(merged: dict[str, Any]) -> None:
    """Install/remove Ruby gems for the given merged profile data."""
    packages: list[dict[str, Any]] = merged.get("gem_packages", [])
    if not packages:
        return

    if not host.get_fact(Which, command="gem"):
        names = ", ".join(p["name"] for p in packages)
        logger.warning(
            "gem not found in PATH — add 'ruby' to brew_packages. "
            f"Skipping gem packages: {names}"
        )
        return

    present = [
        p["name"]
        for p in packages
        if p.get("state", "present") != "absent" and "version" not in p
    ]
    versioned = [
        p for p in packages if "version" in p and p.get("state", "present") != "absent"
    ]
    absent = [p["name"] for p in packages if p.get("state") == "absent"]

    if present:
        gem.packages(
            name=f"Install {len(present)} gem(s)",
            packages=present,
            present=True,
        )
    if absent:
        gem.packages(
            name=f"Uninstall {len(absent)} gem(s)",
            packages=absent,
            present=False,
        )
    for pkg in versioned:
        _versioned_gem(pkg)


def _versioned_gem(pkg: dict[str, Any]) -> None:
    name = pkg["name"]
    version = pkg["version"]
    quoted_name = shlex.quote(name)
    quoted_version = shlex.quote(str(version))
    server.shell(
        name=f"Install gem {name} version {version}",
        commands=[
            f"gem list -i {quoted_name} -v {quoted_version} >/dev/null 2>&1"
            f" || gem install {quoted_name} -v {quoted_version}"
        ],
    )

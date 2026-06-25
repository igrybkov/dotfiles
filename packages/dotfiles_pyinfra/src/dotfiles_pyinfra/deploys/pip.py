"""pip deploy — global Python packages.

Mirrors the logic of ``roles/pip/tasks/main.yml``.

Steps (same as the Ansible role):
  1. Skip entirely if no pip packages are configured
  2. Resolve a pip executable, preferring (in order) a miniconda pip, then
     ``pip3``, then ``pip``. Skip with a log message if none is found.
  3. Install present/latest packages; uninstall absent ones.

Note: pip is resolved at deploy-build time via ``shutil.which`` (it is a
pre-existing tool, unlike npm/gem which may be installed earlier in the same
run).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from pyinfra import logger
from pyinfra.operations import pip


def _resolve_pip() -> str | None:
    """Return the path to a usable pip executable, or ``None`` if absent."""
    miniconda_pip = Path.home() / ".local/share/miniconda3/bin/pip"
    if miniconda_pip.is_file() and os.access(miniconda_pip, os.X_OK):
        return str(miniconda_pip)
    return shutil.which("pip3") or shutil.which("pip")


def deploy(merged: dict[str, Any]) -> None:
    """Install/remove global pip packages for the given merged profile data."""
    packages: list[dict[str, Any]] = merged.get("pip_packages", [])
    if not packages:
        return

    pip_exe = _resolve_pip()
    if not pip_exe:
        names = ", ".join(p["name"] for p in packages)
        logger.warning(
            f"pip not found — add 'python@3' to brew_packages. Skipping pip packages: {names}"
        )
        return

    # Default state is 'latest' to match the Ansible role.
    present = [p["name"] for p in packages if p.get("state", "latest") == "present"]
    latest = [p["name"] for p in packages if p.get("state", "latest") == "latest"]
    absent = [p["name"] for p in packages if p.get("state") == "absent"]

    if present:
        pip.packages(
            name=f"Install {len(present)} pip package(s)",
            packages=present,
            present=True,
            pip=pip_exe,
            virtualenv=None,
        )
    if latest:
        pip.packages(
            name=f"Upgrade {len(latest)} pip package(s) to latest",
            packages=latest,
            present=True,
            latest=True,
            pip=pip_exe,
            virtualenv=None,
        )
    if absent:
        pip.packages(
            name=f"Uninstall {len(absent)} pip package(s)",
            packages=absent,
            present=False,
            pip=pip_exe,
            virtualenv=None,
        )

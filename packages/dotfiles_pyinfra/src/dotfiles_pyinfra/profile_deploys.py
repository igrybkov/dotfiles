"""Profile-level custom deploy discovery and runner.

Each profile may ship a ``deploy.py`` at its root exposing a
``deploy(tags, dotfiles_dir)`` function. These run at the end of the site
deploy, in profile priority order, so a profile can layer in custom pyinfra
ops (e.g. macOS system defaults, profile-specific binaries) that don't fit the
generic config/package deploys.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from pyinfra import logger


def run_profile_deploys(
    profiles: list[Any], tags: set[str], dotfiles_dir: Path
) -> None:
    """Discover and run ``deploy.py`` from each profile in priority order."""
    for p in profiles:  # profiles already sorted by priority ascending
        deploy_py = p.path / "deploy.py"
        if not deploy_py.exists():
            continue
        spec = importlib.util.spec_from_file_location(
            f"profile_deploy_{p.name}", deploy_py
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load {deploy_py}: no importlib spec")
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        if hasattr(mod, "deploy"):
            mod.deploy(tags=tags, dotfiles_dir=dotfiles_dir)

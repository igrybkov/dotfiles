"""Claude Code plugins deploy — marketplaces and plugins.

Mirrors the logic of ``roles/claude_plugins/tasks/main.yml``.

Discovery (which marketplaces are registered, which plugins are installed) runs
at *build time* via subprocess so that we only emit shell operations for the
deltas — registering missing marketplaces, removing stale ones, and
installing/uninstalling plugins to match desired state.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from typing import Any

from pyinfra import logger
from pyinfra.operations import server

_DEFAULT_MARKETPLACE = "claude-plugins-official"


def deploy(merged: dict[str, Any]) -> None:
    """Reconcile Claude plugin marketplaces and plugins with desired state.

    Args:
        merged: Merged profile config. Reads ``claude_plugins`` and
            ``claude_plugin_marketplaces``.
    """
    if shutil.which("claude") is None:
        logger.warning(
            "claude CLI not found in PATH; skipping claude_plugins. Add 'claude-code' to cask_packages to enable."
        )
        return

    plugins: list[dict[str, Any]] = merged.get("claude_plugins", [])
    marketplaces: list[dict[str, Any]] = merged.get("claude_plugin_marketplaces", [])

    _manage_marketplaces(marketplaces)
    _manage_plugins(plugins)


def _manage_marketplaces(marketplaces: list[dict[str, Any]]) -> None:
    """Register present marketplaces and remove absent ones, then refresh."""
    registered = _discover(
        ["claude", "plugin", "marketplace", "list", "--json"], key="name"
    )

    changed = False
    for m in marketplaces:
        state = m.get("state", "present")
        name = m["name"]
        if state != "absent" and name not in registered:
            server.shell(
                name=f"Register plugin marketplace {name}",
                commands=[f"claude plugin marketplace add {shlex.quote(m['path'])}"],
            )
            changed = True
        elif state == "absent" and name in registered:
            server.shell(
                name=f"Remove plugin marketplace {name}",
                commands=[f"claude plugin marketplace remove {shlex.quote(name)}"],
            )
            changed = True

    if changed:
        server.shell(
            name="Update plugin marketplaces",
            commands=["claude plugin marketplace update"],
        )


def _manage_plugins(plugins: list[dict[str, Any]]) -> None:
    """Install present plugins and uninstall absent ones, by ``name@marketplace`` id."""
    installed = _discover(["claude", "plugin", "list", "--json"], key="id")

    for plugin in plugins:
        plugin_id = (
            f"{plugin['name']}@{plugin.get('marketplace', _DEFAULT_MARKETPLACE)}"
        )
        state = plugin.get("state", "present")

        if state == "absent" and plugin_id in installed:
            server.shell(
                name=f"Uninstall plugin {plugin_id}",
                commands=[f"claude plugin uninstall {shlex.quote(plugin_id)}"],
            )
        elif state != "absent" and plugin_id not in installed:
            server.shell(
                name=f"Install plugin {plugin_id}",
                commands=[f"claude plugin install {shlex.quote(plugin_id)}"],
            )


def _discover(command: list[str], key: str) -> set[str]:
    """Run a `--json` claude discovery command and collect the given key into a set.

    Failures (non-zero exit, malformed JSON) degrade to an empty set so the deploy
    falls back to issuing all operations rather than crashing the build.
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        logger.warning(f"Failed to run {' '.join(command)}: {exc}")
        return set()

    try:
        items = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to parse output of {' '.join(command)}: {exc}")
        return set()

    return {item[key] for item in items}

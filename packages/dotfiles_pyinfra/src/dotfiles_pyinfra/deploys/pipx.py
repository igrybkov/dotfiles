"""pipx deploy — Python CLI tools via uv/pipx.

Mirrors the logic of ``roles/pipx/tasks/main.yml``.

Three package categories, distinguished by their keys:
  * PyPI packages   — neither ``path`` nor ``git`` (install from PyPI)
  * Local editable  — has ``path`` (install ``--editable`` from a local dir)
  * Git packages    — has ``git`` (install from a git URL)

Installer selection (build-time): prefer ``uv tool`` when available, fall back
to ``pipx``. ``shutil.which`` here is a *selector* (which installer to call),
not an availability *guard* — both branches still install, so a fresh machine
where brew installed uv/pipx earlier in the same run is handled correctly.

Idempotency is expressed inline in the shell so it degrades gracefully when the
tool is still being installed earlier in the run:
``uv tool list 2>/dev/null | grep -q "^name " || uv tool install name``.
"""

from __future__ import annotations

import shlex
import shutil
from typing import Any

from pyinfra.operations import server


def deploy(merged: dict[str, Any]) -> None:
    """Install/remove Python CLI tools for the given merged profile data."""
    packages: list[dict[str, Any]] = merged.get("pipx_packages", [])
    if not packages:
        return

    use_uv = shutil.which("uv") is not None
    use_pipx = shutil.which("pipx") is not None

    # Split packages by category.
    local = [p for p in packages if "path" in p]
    git = [p for p in packages if "git" in p and "path" not in p]
    pypi = [p for p in packages if "path" not in p and "git" not in p]

    # Uninstall absent local packages FIRST so source-based reinstalls below can
    # replace them cleanly (e.g. switching from editable-local to a git URL).
    for pkg in local:
        if pkg.get("state", "present") == "absent":
            _uninstall(pkg["name"], use_uv=use_uv, use_pipx=use_pipx)

    for pkg in pypi:
        _pypi_package(pkg, use_uv=use_uv, use_pipx=use_pipx)

    for pkg in local:
        if pkg.get("state", "present") != "absent":
            _local_package(pkg, use_uv=use_uv, use_pipx=use_pipx)

    for pkg in git:
        _git_package(pkg, use_uv=use_uv, use_pipx=use_pipx)


# ---------------------------------------------------------------------------
# Build-flag helpers (build_deps -> CFLAGS / LDFLAGS)
# ---------------------------------------------------------------------------


def _env_prefix(pkg: dict[str, Any]) -> str:
    """Build a shell ``VAR=... VAR=...`` prefix from build_deps + explicit env.

    ``build_deps`` are resolved at run time via ``brew --prefix <dep>`` and
    folded into ``CFLAGS``/``LDFLAGS``. Explicit ``env`` entries are emitted
    afterwards so they take precedence over the derived build flags.
    """
    parts: list[str] = []

    build_deps = pkg.get("build_deps") or []
    if build_deps:
        include_parts: list[str] = []
        lib_parts: list[str] = []
        for dep in build_deps:
            quoted = shlex.quote(str(dep))
            include_parts.append(f'-I"$(brew --prefix {quoted})/include"')
            lib_parts.append(f'-L"$(brew --prefix {quoted})/lib"')
        parts.append(f"CFLAGS={shlex.quote(' '.join(include_parts))}")
        parts.append(f"LDFLAGS={shlex.quote(' '.join(lib_parts))}")

    # Explicit env overrides build flags — emit after so the later assignment wins.
    for key, value in (pkg.get("env") or {}).items():
        parts.append(f"{key}={shlex.quote(str(value))}")

    # CFLAGS/LDFLAGS contain unescaped $() that must run; do not quote the whole
    # prefix. The build-flag values are single-quoted around an embedded $(), so
    # the command substitution still expands — that is intentional.
    if not parts:
        return ""
    return " ".join(parts) + " "


# ---------------------------------------------------------------------------
# PyPI packages
# ---------------------------------------------------------------------------


def _pypi_package(pkg: dict[str, Any], *, use_uv: bool, use_pipx: bool) -> None:
    name = pkg["name"]
    quoted = shlex.quote(name)
    state = pkg.get("state", "present")

    if state == "absent":
        _uninstall(name, use_uv=use_uv, use_pipx=use_pipx)
        return

    env_prefix = _env_prefix(pkg)
    if use_uv:
        server.shell(
            name=f"Install pipx package {name} (uv)",
            commands=[
                f'uv tool list 2>/dev/null | grep -q "^{name} "'
                f" || {env_prefix}uv tool install {quoted}"
            ],
        )
    elif use_pipx:
        server.shell(
            name=f"Install pipx package {name} (pipx)",
            commands=[
                f"pipx list --short 2>/dev/null | grep -q {quoted}"
                f" || {env_prefix}pipx install {quoted}"
            ],
        )


# ---------------------------------------------------------------------------
# Local editable packages
# ---------------------------------------------------------------------------


def _local_package(pkg: dict[str, Any], *, use_uv: bool, use_pipx: bool) -> None:
    name = pkg["name"]
    path = pkg["path"]
    quoted_path = shlex.quote(str(path))
    env_prefix = _env_prefix(pkg)

    if use_uv:
        # uv re-resolves dependencies every run by design; no idempotency grep.
        server.shell(
            name=f"Install local package {name} (uv editable)",
            commands=[f"{env_prefix}uv tool install --editable {quoted_path}"],
        )
    elif use_pipx:
        # pipx fallback: force reinstall to pick up dependency changes.
        server.shell(
            name=f"Install local package {name} (pipx editable)",
            commands=[f"{env_prefix}pipx install --editable --force {quoted_path}"],
        )


# ---------------------------------------------------------------------------
# Git packages
# ---------------------------------------------------------------------------


def _git_package(pkg: dict[str, Any], *, use_uv: bool, use_pipx: bool) -> None:
    name = pkg["name"]
    quoted_name = shlex.quote(name)
    quoted_git = shlex.quote(pkg["git"])
    state = pkg.get("state", "present")

    if state == "absent":
        _uninstall(name, use_uv=use_uv, use_pipx=use_pipx)
        return

    if use_uv:
        server.shell(
            name=f"Install git package {name} (uv)",
            commands=[
                f'uv tool list 2>/dev/null | grep -q "^{name} "'
                f" || uv tool install --from {quoted_git} {quoted_name}"
            ],
        )
    elif use_pipx:
        server.shell(
            name=f"Install git package {name} (pipx)",
            commands=[
                f"pipx list --short 2>/dev/null | grep -q {quoted_name}"
                f" || pipx install {quoted_git}"
            ],
        )


# ---------------------------------------------------------------------------
# Shared uninstall
# ---------------------------------------------------------------------------


def _uninstall(name: str, *, use_uv: bool, use_pipx: bool) -> None:
    quoted = shlex.quote(name)
    if use_uv:
        server.shell(
            name=f"Uninstall pipx package {name} (uv)",
            commands=[f"uv tool uninstall {quoted} 2>/dev/null || true"],
        )
    elif use_pipx:
        server.shell(
            name=f"Uninstall pipx package {name} (pipx)",
            commands=[f"pipx uninstall {quoted} 2>/dev/null || true"],
        )

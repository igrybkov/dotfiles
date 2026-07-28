"""Homebrew deploy — taps, formulas, casks.

Mirrors the logic of ``roles/brew_packages/tasks/main.yml``.

Ordering (same as the Ansible role):
  1. Add taps that are present
  2. Uninstall absent formulas
  3. Install/upgrade present and latest formulas; versioned installs via shell
  4. Uninstall absent casks
  5. Install/upgrade present and latest casks; versioned casks via shell
  6. Remove absent taps (after packages from them are gone)
  7. If brew_upgrade_all: upgrade everything
"""

from __future__ import annotations

from typing import Any

from pyinfra.operations import brew, server


def deploy(merged: dict[str, Any]) -> None:
    """Run all Homebrew operations for the given merged profile data."""
    taps: list[dict[str, Any]] = merged.get("brew_taps", [])
    packages: list[dict[str, Any]] = merged.get("brew_packages", [])
    casks: list[dict[str, Any]] = merged.get("cask_packages", [])
    upgrade_all: bool = merged.get("brew_upgrade_all", False)

    _taps(taps)
    _formulas(packages)
    _casks(casks)
    _remove_taps(taps)

    if upgrade_all:
        # brew upgrade exits 1 when a single cask fails (e.g. the app is
        # running) even though everything else upgraded — the Ansible role
        # tolerated this via failed_when; don't let it abort the deploy.
        brew.packages(
            name="Upgrade all Homebrew packages",
            upgrade=True,
            _ignore_errors=True,
        )


# ---------------------------------------------------------------------------
# Taps
# ---------------------------------------------------------------------------


def _taps(taps: list[dict[str, Any]]) -> None:
    present = [t for t in taps if t.get("state", "present") != "absent"]
    for tap in present:
        brew.tap(
            name=f"Add tap {tap['name']}",
            src=tap["name"],
            present=True,
        )


def _remove_taps(taps: list[dict[str, Any]]) -> None:
    absent = [t for t in taps if t.get("state") == "absent"]
    for tap in absent:
        brew.tap(
            name=f"Remove tap {tap['name']}",
            src=tap["name"],
            present=False,
        )


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------


def _formulas(packages: list[dict[str, Any]]) -> None:
    absent = [p["name"] for p in packages if p.get("state") == "absent"]
    latest = [
        p["name"] for p in packages if p.get("state") == "latest" and "version" not in p
    ]
    versioned = [p for p in packages if "version" in p and p.get("state") != "absent"]
    present = [
        p["name"]
        for p in packages
        if p.get("state", "present") == "present" and "version" not in p
    ]

    if absent:
        brew.packages(
            name=f"Uninstall {len(absent)} brew {'package' if len(absent) == 1 else 'packages'}",
            packages=absent,
            present=False,
        )
    if present:
        brew.packages(
            name=f"Install {len(present)} brew {'package' if len(present) == 1 else 'packages'}",
            packages=present,
            present=True,
        )
    if latest:
        brew.packages(
            name=f"Upgrade {len(latest)} brew {'package' if len(latest) == 1 else 'packages'} to latest",
            packages=latest,
            present=True,
            latest=True,
        )
    for pkg in versioned:
        _versioned_formula(pkg)


def _versioned_formula(pkg: dict[str, Any]) -> None:
    formula = f"{pkg['name']}@{pkg['version']}"
    server.shell(
        name=f"Install formula {formula}",
        commands=[
            f"brew list --versions {formula} | grep -q '{pkg['version']}'"
            f" || brew install {formula}"
        ],
    )


# ---------------------------------------------------------------------------
# Casks
# ---------------------------------------------------------------------------


def _casks(casks: list[dict[str, Any]]) -> None:
    absent = [c["name"] for c in casks if c.get("state") == "absent"]
    latest = [
        c["name"] for c in casks if c.get("state") == "latest" and "version" not in c
    ]
    versioned = [c for c in casks if "version" in c and c.get("state") != "absent"]
    present = [
        c["name"]
        for c in casks
        if c.get("state", "present") == "present" and "version" not in c
    ]

    for name in absent:
        brew.casks(
            name=f"Uninstall cask {name}",
            casks=[name],
            present=False,
        )
    for name in present:
        brew.casks(
            name=f"Install cask {name}",
            casks=[name],
            present=True,
        )
    for name in latest:
        brew.casks(
            name=f"Upgrade cask {name} to latest",
            casks=[name],
            present=True,
            latest=True,
        )
    for cask in versioned:
        _versioned_cask(cask)


def _versioned_cask(cask: dict[str, Any]) -> None:
    server.shell(
        name=f"Install cask {cask['name']} version {cask['version']}",
        commands=[
            f"brew list --cask --versions {cask['name']}"
            f" | grep -q '{cask['version']}'"
            f" || brew install --adopt --cask {cask['name']}"
        ],
    )

"""mas deploy — Mac App Store apps.

Mirrors the logic of ``roles/mas/tasks/main.yml``.

Steps (same as the Ansible role):
  1. Install present packages not already installed
  2. Uninstall absent packages that are installed; remove their ``.app`` bundle
  3. Optionally ``mas upgrade`` everything

Two-phase caveat: ``deploy()`` runs at *build* time and only emits operations;
it never sees the runtime stdout of ``mas list`` or ``mas install``. So the
"installed?" check and the error-collection cannot happen in Python the way the
Ansible role does — both are realized at the *shell* level:

  * each ``mas install``/``uninstall`` is gated by an inline
    ``mas list | grep -q ...`` so it is idempotent and degrades gracefully when
    ``mas`` was only just installed by brew earlier in the same run;
  * failures are appended to a per-run error file which a finalizing op turns
    into ``.cache/mas_errors.json`` (or removes when empty).
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from pyinfra.operations import server


def deploy(merged: dict[str, Any], dotfiles_dir: Path) -> None:
    """Install/remove/upgrade Mac App Store apps for the merged profile data."""
    packages: list[dict[str, Any]] = merged.get("mas_packages", [])
    upgrade_all: bool = merged.get("mas_upgrade_all", False)
    if not packages and not upgrade_all:
        return

    cache_dir = dotfiles_dir / ".cache"
    err_file = cache_dir / "mas_errors.json"
    # A scratch file we append raw error lines to during the run; the finalizer
    # converts it into a JSON array (or removes the JSON file when empty).
    raw_err = cache_dir / "mas_errors.raw"
    quoted_cache = shlex.quote(str(cache_dir))
    quoted_err = shlex.quote(str(err_file))
    quoted_raw = shlex.quote(str(raw_err))

    # Reset state: ensure cache dir exists and start from an empty error file.
    server.shell(
        name="Prepare mas error cache",
        commands=[f"mkdir -p {quoted_cache} && : > {quoted_raw}"],
    )

    for pkg in packages:
        if "id" not in pkg:
            continue
        app_id = str(pkg["id"])
        name = pkg.get("name", app_id)
        state = pkg.get("state", "present")

        if state == "absent":
            _uninstall(pkg, app_id, name, quoted_raw)
        else:
            _install(app_id, name, quoted_raw)

    if upgrade_all:
        server.shell(
            name="Upgrade Mac App Store packages",
            commands=[
                f"mas upgrade 2>>{quoted_raw}"
                f" || echo 'Failed to upgrade packages' >> {quoted_raw}"
            ],
            _sudo=True,
        )

    # Finalize: if any errors were recorded, render them to JSON; else drop the
    # JSON file so the final summary stays clean.
    server.shell(
        name="Finalize mas error report",
        commands=[
            f"if [ -s {quoted_raw} ]; then "
            f"python3 -c "
            f'"import json,sys; '
            f'print(json.dumps([l.rstrip(chr(10)) for l in sys.stdin if l.strip()]))" '
            f"< {quoted_raw} > {quoted_err}; "
            f"else rm -f {quoted_err}; fi; "
            f"rm -f {quoted_raw}"
        ],
    )


def _install(app_id: str, name: str, quoted_raw: str) -> None:
    quoted_id = shlex.quote(app_id)
    # grep -F: fixed-string match on "<id> " anchored at line start via the
    # leading space pattern. shlex.quote keeps the whole pattern (incl. id and
    # trailing space) shell-safe as a single argument.
    pattern = shlex.quote(f"^{app_id} ")
    err_msg = shlex.quote(f"Failed to install {name}")
    server.shell(
        name=f"Install Mac App Store package {name}",
        commands=[
            f"(mas list 2>/dev/null || echo '') | grep -q {pattern}"
            f" || mas install {quoted_id} 2>>{quoted_raw}"
            f" || echo {err_msg} >> {quoted_raw}"
        ],
    )


def _uninstall(pkg: dict[str, Any], app_id: str, name: str, quoted_raw: str) -> None:
    quoted_id = shlex.quote(app_id)
    pattern = shlex.quote(f"^{app_id} ")
    err_msg = shlex.quote(f"Failed to uninstall {name}")
    server.shell(
        name=f"Uninstall Mac App Store package {name}",
        commands=[
            f"! (mas list 2>/dev/null || echo '') | grep -q {pattern}"
            f" || mas uninstall {quoted_id} 2>>{quoted_raw}"
            f" || echo {err_msg} >> {quoted_raw}"
        ],
    )
    # Remove the app bundle too (requires sudo, like the Ansible role's become).
    if pkg.get("name"):
        app_path = shlex.quote(f"/Applications/{pkg['name']}.app")
        server.shell(
            name=f"Remove app bundle for {name}",
            commands=[f"rm -rf {app_path}"],
            _sudo=True,
        )

"""gh_repos deploy — clone/update GitHub repositories.

Mirrors the logic of ``roles/gh_repos/tasks/main.yml`` + ``repo.yml``.

Each repo entry: ``{"repo": "owner/repo", "state": ..., "dest": ..., "branch":
..., "tag": ...}``. Destination defaults to ``{gh_repos_default_dest}/{name}``.
``tag`` takes precedence over ``branch``.

States:
  * ``present`` — clone if missing; checkout branch/tag once (default)
  * ``latest``  — clone if missing; then fetch + pull (or re-checkout the tag)
  * ``absent``  — remove the destination directory

Existence is checked inline in the shell (``[ -d dest ] || gh repo clone ...``)
so the ops degrade gracefully and stay idempotent — no ``which gh`` guard and no
"install gh via brew" task (brew already ran earlier in the same pyinfra run).
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from pyinfra.operations import server


def deploy(merged: dict[str, Any]) -> None:
    """Clone/update/remove GitHub repositories for the merged profile data."""
    repos: list[dict[str, Any]] = merged.get("gh_repos", [])
    if not repos:
        return

    default_dest = merged.get("gh_repos_default_dest", "~/Projects")
    default_base = str(Path(default_dest).expanduser())

    for repo in repos:
        _process_repo(repo, default_base)


def _process_repo(repo: dict[str, Any], default_base: str) -> None:
    repo_spec = repo["repo"]
    repo_name = repo_spec.split("/")[-1]
    dest = repo.get("dest", f"{default_base}/{repo_name}")
    dest = str(Path(dest).expanduser())
    state = repo.get("state", "present")
    branch = repo.get("branch")
    tag = repo.get("tag")

    quoted_spec = shlex.quote(repo_spec)
    quoted_dest = shlex.quote(dest)

    if state == "absent":
        server.shell(
            name=f"Remove repo {repo_spec}",
            commands=[f"rm -rf {quoted_dest}"],
        )
        return

    # Clone when the destination does not yet exist. Create the parent dir first
    # (the Ansible role ensures the parent exists before cloning).
    parent = shlex.quote(str(Path(dest).parent))
    try:
        dest_label = "~/" + str(Path(dest).relative_to(Path.home()))
    except ValueError:
        dest_label = dest
    server.shell(
        name=f"Clone repo {repo_spec} → {dest_label}",
        commands=[
            f"[ -d {quoted_dest} ]"
            f" || (mkdir -p {parent} && gh repo clone {quoted_spec} {quoted_dest})"
        ],
    )

    # state=latest: bring an existing checkout up to date. With a tag we
    # re-checkout the tag after fetching; otherwise fast-forward pull.
    if state == "latest":
        if tag:
            quoted_tag = shlex.quote(str(tag))
            server.shell(
                name=f"Update repo {repo_spec} to tag {tag}",
                commands=[
                    f"[ -d {quoted_dest} ] || exit 0; "
                    f"git -C {quoted_dest} fetch --all --tags"
                    f" && git -C {quoted_dest} checkout {quoted_tag}"
                ],
            )
        else:
            server.shell(
                name=f"Update repo {repo_spec} (fetch + pull)",
                commands=[
                    f"[ -d {quoted_dest} ] || exit 0; "
                    f"git -C {quoted_dest} fetch --all --tags"
                    f" && git -C {quoted_dest} pull --ff-only"
                ],
            )

    # On first clone (present or latest) honour an explicit branch/tag checkout.
    # tag takes precedence over branch. For state=latest the update op above
    # already handles the tag, so only the branch needs an explicit checkout.
    if tag and state != "latest":
        quoted_tag = shlex.quote(str(tag))
        server.shell(
            name=f"Checkout tag {tag} in {repo_spec}",
            commands=[f"git -C {quoted_dest} checkout {quoted_tag}"],
        )
    elif branch:
        quoted_branch = shlex.quote(str(branch))
        server.shell(
            name=f"Checkout branch {branch} in {repo_spec}",
            commands=[f"git -C {quoted_dest} checkout {quoted_branch}"],
        )

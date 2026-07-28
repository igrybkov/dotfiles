"""Agents profile custom deploy — plannotator binary.

Ports ``profiles/agents/tasks/plannotator.yml``: installs/updates the
``plannotator`` binary from GitHub releases via the shared ``github_binary``
deploy. Version resolution and idempotency are handled inside that deploy.
"""

from __future__ import annotations

from pathlib import Path

from dotfiles_pyinfra.deploys import github_binary as github_binary_deploy
from dotfiles_pyinfra.tags import tag_selected


def deploy(tags: set[str], dotfiles_dir: Path) -> None:
    if not tag_selected("github-binary", tags) and not tag_selected(
        "coding-agents", tags
    ):
        return

    github_binary_deploy.deploy(
        merged={
            "github_binaries": [
                {
                    "name": "plannotator",
                    "repo": "backnotprop/plannotator",
                    "asset_darwin_arm64": "plannotator-darwin-arm64",
                    "asset_darwin_x86_64": "plannotator-darwin-x64",
                    "asset_linux": "plannotator-linux-x64",
                    "type": "binary",
                }
            ]
        }
    )

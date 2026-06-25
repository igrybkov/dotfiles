"""JSON config deploy — deep-merge settings into JSON files.

Mirrors the logic of ``roles/json_config/tasks/`` (``main.yml`` +
``apply_config.yml``).

Variable from merged config: ``json_configs`` — a list of items::

    - file: ~/.claude/settings.json
      content: {key: value, ...}
      create_file: true   # optional, default false

For each item the current file content is read at deploy-build time and
deep-merged with ``content``. Reading at build time is correct here: these are
pre-existing config files (or freshly created ones) whose current state must be
known to compute the merge, and json_config does not depend on any prior
file-mutating operation. This matches what the Ansible role does (``slurp`` +
``combine(recursive=true)``).

The merge is destructive on shared config files, so this runs against
``merged_all`` (every enabled profile), not the selected subset.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from pyinfra import logger
from pyinfra.operations import files

from dotfiles_pyinfra.merge import deep_merge


def deploy(merged: dict[str, Any]) -> None:
    """Apply all JSON config merges for the given merged profile data."""
    configs: list[dict[str, Any]] = merged.get("json_configs", [])
    for item in configs:
        _apply(item)


def _apply(item: dict[str, Any]) -> None:
    path = Path(item["file"]).expanduser()
    create_file: bool = bool(item.get("create_file", False))
    content: dict[str, Any] = item.get("content") or {}

    exists = path.exists()
    if not exists and not create_file:
        logger.debug(
            f"json_config: skipping {path} — file doesn't exist and create_file is false"
        )
        return

    # Ensure the parent directory exists before writing.
    files.directory(
        name=f"Ensure parent dir for {path}",
        path=str(path.parent),
        present=True,
        mode="755",
    )

    # Read and parse the current content at build time (empty when the file does
    # not exist yet). An empty file is treated as an empty object.
    if exists:
        current_text = path.read_text()
        current = json.loads(current_text) if current_text.strip() else {}
    else:
        current = {}

    merged_content = deep_merge(current, content)

    if exists and merged_content == current:
        # Nothing changed — emit no write operation.
        return

    new_text = json.dumps(merged_content, indent=2, sort_keys=True) + "\n"
    files.put(
        name=f"Write JSON config {path}",
        src=io.BytesIO(new_text.encode()),
        dest=str(path),
        mode="644",
    )

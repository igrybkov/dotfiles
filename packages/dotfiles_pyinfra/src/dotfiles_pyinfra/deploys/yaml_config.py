"""YAML config deploy — deep-merge settings into YAML files.

Mirrors the logic of ``roles/yaml_config/tasks/`` (``main.yml`` +
``apply_config.yml``).

Variable from merged config: ``yaml_configs`` — a list of items::

    - file: ~/.config/mise/config.toml
      content: {key: value, ...}
      create_file: true   # optional, default false

For each item the current file content is read at deploy-build time and
deep-merged with ``content``. Reading at build time is correct here: these are
pre-existing config files (or freshly created ones) whose current state must be
known to compute the merge, and yaml_config does not depend on any prior
file-mutating operation. This matches what the Ansible role does (``slurp`` +
``combine(recursive=true)``).

``ruamel.yaml`` is used for round-trip parsing/serialization. The merge itself
runs on plain Python dicts: the current document is normalized via
``json.loads(json.dumps(...))`` to strip ``CommentedMap`` / ``CommentedSeq``
wrappers before merging, then the plain result is dumped back out.

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
from ruamel.yaml import YAML

from dotfiles_pyinfra.merge import deep_merge

_ryaml = YAML()
_ryaml.preserve_quotes = True


def deploy(merged: dict[str, Any]) -> None:
    """Apply all YAML config merges for the given merged profile data."""
    configs: list[dict[str, Any]] = merged.get("yaml_configs", [])
    for item in configs:
        _apply(item)


def _apply(item: dict[str, Any]) -> None:
    path = Path(item["file"]).expanduser()
    create_file: bool = bool(item.get("create_file", False))
    content: dict[str, Any] = item.get("content") or {}

    exists = path.exists()
    if not exists and not create_file:
        logger.debug(
            f"yaml_config: skipping {path} — file doesn't exist and create_file is false"
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
    # not exist yet, or when ruamel returns None for an empty document).
    if exists:
        loaded = _ryaml.load(path.read_text())
        # Normalize ruamel's CommentedMap/CommentedSeq to plain Python objects
        # so deep_merge (which operates on plain dicts) behaves predictably.
        current = json.loads(json.dumps(loaded)) if loaded is not None else {}
    else:
        current = {}

    merged_content = deep_merge(current, content)

    if exists and merged_content == current:
        # Nothing changed — emit no write operation.
        return

    buf = io.StringIO()
    _ryaml.dump(merged_content, buf)
    new_text = buf.getvalue()
    files.put(
        name=f"Write YAML config {path}",
        src=io.BytesIO(new_text.encode()),
        dest=str(path),
        mode="644",
    )

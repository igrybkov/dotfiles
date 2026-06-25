"""Agent instructions deploy — assemble AGENT.md fragments into destinations.

Mirrors the logic of ``roles/agent_instructions/tasks/``.

Fragments named ``{NN}-{section}.md`` live under each profile's
``files/AGENT.md`` directory. They are collected across all profiles, sorted by
``(priority, filename)``, and concatenated into one or more destination files
(e.g. ``~/.claude/CLAUDE.md``, ``~/.cursor/rules/agent-instructions.mdc``).

Fragment contents are read at build time, so the assembled output is materialized
when the deploy is generated rather than on the target host.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from pyinfra.operations import files


def deploy(profiles: list[Any], merged: dict[str, Any]) -> None:
    """Collect AGENT.md fragments and write them to each configured destination.

    Args:
        profiles: Profiles sorted by priority ascending. Each must expose
            ``name``, ``path``, and ``priority`` attributes.
        merged: Merged profile config; ``agent_instructions_destinations`` lists
            the output files (each with a ``path`` and optional ``frontmatter``).
    """
    # Step 1: collect fragments across all profiles.
    fragments: list[dict[str, Any]] = []
    for p in profiles:
        fragment_dir = p.path / "files/AGENT.md"
        if not fragment_dir.is_dir():
            continue
        for file_path in sorted(fragment_dir.glob("*.md")):
            if not file_path.is_file():
                continue
            fragments.append(
                {
                    "path": file_path,
                    "profile": p.name,
                    "priority": p.priority,
                    "filename": file_path.name,
                }
            )

    if not fragments:
        return

    # Step 2: sort by (priority, filename) to get a stable, ordered assembly.
    fragments.sort(key=lambda f: (f["priority"], f["filename"]))

    # Step 3: resolve destinations.
    destinations: list[dict[str, Any]] = merged.get(
        "agent_instructions_destinations", []
    )

    # Step 4: assemble and write each destination.
    for dest in destinations:
        _write_destination(dest, fragments)


def _friendly(path: Path) -> str:
    """Return a ~-shortened path string for operation labels."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _write_destination(dest: dict[str, Any], fragments: list[dict[str, Any]]) -> None:
    """Assemble fragment contents (plus optional frontmatter) and write one file."""
    dest_path = Path(dest["path"]).expanduser()

    files.directory(
        name=f"Ensure directory exists for {_friendly(dest_path.parent)}",
        path=str(dest_path.parent),
        mode="755",
    )

    parts: list[str] = []

    frontmatter = dest.get("frontmatter")
    if frontmatter:
        lines = ["---"]
        # json.dumps mirrors Ansible's `| to_json`: booleans -> true/false,
        # strings -> quoted JSON strings, etc.
        lines.extend(
            f"{key}: {json.dumps(value)}" for key, value in frontmatter.items()
        )
        lines.append("---")
        lines.append("")  # blank line separating frontmatter from body
        parts.append("\n".join(lines) + "\n")

    # Concatenate fragment bodies, joined with a newline between (not before first).
    bodies = [fragment["path"].read_text() for fragment in fragments]
    parts.append("\n".join(bodies))

    content = "".join(parts)

    files.put(
        name=f"Assemble agent instructions → {_friendly(dest_path)}",
        src=io.BytesIO(content.encode()),
        dest=str(dest_path),
        mode="644",
    )

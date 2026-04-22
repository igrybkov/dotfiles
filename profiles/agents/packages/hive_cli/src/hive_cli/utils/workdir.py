"""Workdir override selection for the interactive worktree picker."""

from __future__ import annotations

from pathlib import Path

from ..config import get_agent_config, get_settings
from ..git import expand_path, get_main_repo
from .fuzzy import FuzzyItem, fuzzy_select


def select_workdir(
    current_agent: str | None,
    current_override: Path | None = None,
) -> Path | None:
    """Show picker for overriding the session cwd with one of the extra_dirs.

    The outer picker decides the "primary" path (main repo or a worktree).
    This sub-picker lets the user swap that primary with one of the extra
    directories configured in `extra_dirs`. The displaced primary is added
    to the extras list at launch time (in exec_runner).

    Args:
        current_agent: Active agent name, used to warn if the agent has no
            extra_dirs_flag (meaning the displaced primary can't be added back).
        current_override: Currently-active override path, marked in the list.

    Returns:
        Resolved absolute Path to use as the new cwd, or None if cancelled.
    """
    settings = get_settings()
    dirs = settings.extra_dirs

    if not dirs:
        return None

    main_repo = get_main_repo()
    resolved = [expand_path(d, main_repo) for d in dirs]

    # Build list items, marking the current override if any.
    items: list[FuzzyItem] = []
    current_idx = 0
    for i, path in enumerate(resolved):
        is_current = current_override is not None and path == current_override
        if is_current:
            current_idx = i
        items.append(
            FuzzyItem(
                text=str(path),
                value=str(path),
                meta="← current" if is_current else "",
                style="green" if is_current else "",
            )
        )

    # Header warns when the current agent can't accept the displaced primary.
    agent_cfg = get_agent_config(current_agent) if current_agent else None
    if agent_cfg and not agent_cfg.extra_dirs_flag:
        header = (
            f"Override workdir <red>(warning: agent '{current_agent}' has no "
            f"extra_dirs_flag — original workdir will be dropped)</red>"
        )
    else:
        header = "Override workdir <dim>(Esc to keep default)</dim>"

    selected = fuzzy_select(
        items=items,
        prompt_text=">",
        header=header,
        hint="</dim><b>Enter</b><dim> select  </dim><b>Esc</b><dim> back",
        initial_selection=current_idx,
    )

    return Path(selected) if selected else None

"""Zellij terminal multiplexer integration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..config import get_runtime_settings


def is_running_in_zellij() -> bool:
    """Check if we're running inside a Zellij session."""
    return get_runtime_settings().in_zellij


def rename_pane(name: str) -> None:
    """Rename the current Zellij pane.

    Args:
        name: New name for the pane.

    Note:
        This is a no-op if not running inside Zellij.
        Calls undo-rename-pane first to clear any previous rename.
        Note: undo-rename-pane only clears user renames, NOT layout-defined names.
        Layout names remain as the base, and rename-pane appends to them.
    """
    if not is_running_in_zellij():
        return

    # Clear any previous user rename (not layout-defined names)
    subprocess.run(
        ["zellij", "action", "undo-rename-pane"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        ["zellij", "action", "rename-pane", name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def append_to_pane_title(value: str) -> bool:
    """Append value to current Zellij pane title.

    Trims whitespace from value and prepends a single space.

    Args:
        value: Value to append to the pane title.

    Returns:
        True if running in Zellij and title was updated, False otherwise.
    """
    if not is_running_in_zellij():
        return False

    value = value.strip()
    if not value:
        return False

    subprocess.run(
        ["zellij", "action", "rename-pane", f" {value}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def _get_state_file() -> Path | None:
    """Get path to pane state file, or None if not in Zellij.

    State files are stored at /tmp/hive-zellij/{session}/{pane_id}.json
    """
    if not is_running_in_zellij():
        return None

    rt = get_runtime_settings()
    session = rt.zellij_session_name
    pane_id = rt.zellij_pane_id
    state_dir = Path("/tmp/hive-zellij") / session
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{pane_id}.json"


def _read_state() -> dict:
    """Read pane title state from file."""
    state_file = _get_state_file()
    if state_file and state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"status": None, "branch": None, "custom_title": None}


def _write_state(state: dict) -> None:
    """Write pane title state to file."""
    state_file = _get_state_file()
    if state_file:
        state_file.write_text(json.dumps(state))


def rebuild_pane_title() -> bool:
    """Rebuild and set pane title from stored state.

    Title format depends on context:
    - With HIVE_PANE_ID (in layout): [{agent}] {status} [{branch}] {custom_title}
      (Layout provides "c{id}: Name" as base name, we append agent and branch info)
    - Without HIVE_PANE_ID: {agent}-{pane_id} {status} [{branch}] {custom_title}
      or falls back to cwd relative to home

    Returns:
        True if title was updated, False if not in Zellij.
    """
    if not is_running_in_zellij():
        return False

    state = _read_state()
    rt = get_runtime_settings()
    pane_id = rt.pane_id
    agent = rt.agent

    # Build title parts
    # When HIVE_PANE_ID is set, we're in a layout that already defines
    # the base pane name (e.g., "c2: Bohdan"). Since rename-pane appends
    # to the layout name, we should NOT include the base name prefix.
    parts: list[str] = []

    if not pane_id:
        # Not in layout - need to set the full name including prefix
        if agent:
            # Use ZELLIJ_PANE_ID as fallback for pane numbering
            zellij_pane_id = rt.zellij_pane_id
            parts.append(f"{agent}-{zellij_pane_id}")
        else:
            # Fallback to current directory path relative to home
            cwd = Path.cwd()
            try:
                relative = cwd.relative_to(Path.home())
                parts.append(f"~/{relative}")
            except ValueError:
                # cwd is not under home, use absolute path
                parts.append(str(cwd))

    # When in layout, add agent name in brackets
    if pane_id and agent:
        parts.append(f"[{agent}]")

    if state.get("status"):
        parts.append(state["status"])

    if state.get("branch"):
        parts.append(f"[{state['branch']}]")

    if state.get("custom_title"):
        parts.append(state["custom_title"])

    title = " ".join(parts)

    # When appending to layout name, add leading space
    if pane_id and title:
        title = f" {title}"

    rename_pane(title)
    return True


def set_pane_status(status: str | None) -> bool:
    """Set agent status and rebuild title.

    Args:
        status: Status string (e.g., "[working]", "[idle]"), or None to clear.

    Returns:
        True if title was updated, False if not in Zellij.
    """
    if not is_running_in_zellij():
        return False
    state = _read_state()
    state["status"] = status.strip() if status else None
    _write_state(state)
    return rebuild_pane_title()


def set_pane_branch(branch: str | None) -> bool:
    """Set branch and rebuild title.

    Args:
        branch: Branch name, or None to clear.

    Returns:
        True if title was updated, False if not in Zellij.
    """
    if not is_running_in_zellij():
        return False
    state = _read_state()
    state["branch"] = branch.strip() if branch else None
    _write_state(state)
    return rebuild_pane_title()


def set_pane_custom_title(title: str | None) -> bool:
    """Set custom title suffix and rebuild title.

    Args:
        title: Custom title suffix, or None to clear.

    Returns:
        True if title was updated, False if not in Zellij.
    """
    if not is_running_in_zellij():
        return False
    state = _read_state()
    state["custom_title"] = title.strip() if title else None
    _write_state(state)
    return rebuild_pane_title()

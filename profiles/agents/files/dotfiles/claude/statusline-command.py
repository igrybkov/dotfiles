#!/usr/bin/env python3
"""Claude Code status line - inspired by Starship prompt."""

import json
import os
import subprocess
import sys

# ANSI colors
CYAN = "\033[1;36m"
MAGENTA = "\033[1;35m"
BLUE = "\033[1;34m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
GREEN = "\033[1;32m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_git_branch(cwd: str) -> str:
    """Get current git branch name."""
    git_dir = os.path.join(cwd, ".git")
    if not os.path.exists(git_dir):
        # Check if we're in a subdirectory of a git repo
        try:
            result = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode != 0:
                return ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    try:
        result = subprocess.run(
            ["git", "-C", cwd, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        # Detached HEAD - get short commit hash
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ""


def main() -> None:
    data = json.load(sys.stdin)

    # Extract values
    cwd = data.get("workspace", {}).get("current_dir") or data.get("cwd", "")
    model = data.get("model", {}).get("display_name", "Claude")
    remaining = data.get("context_window", {}).get("remaining_percentage")
    vim_mode = data.get("vim", {}).get("mode")
    output_style = data.get("output_style", {}).get("name")

    # Build components
    components = []

    # Directory (replace home with ~)
    home = os.path.expanduser("~")
    display_dir = cwd.replace(home, "~") if cwd.startswith(home) else cwd
    components.append(f"{CYAN}{display_dir}{RESET}")

    # Git branch
    git_branch = get_git_branch(cwd)
    if git_branch:
        components.append(f"{MAGENTA}{git_branch}{RESET}")

    # Model name (remove "Claude " prefix)
    model_short = model.replace("Claude ", "")
    components.append(f"{BLUE}{model_short}{RESET}")

    # Output style (if not default)
    if output_style and output_style != "default":
        components.append(f"{YELLOW}{output_style}{RESET}")

    # Context remaining (only when low)
    if remaining is not None:
        remaining_int = int(remaining)
        if remaining_int < 30:
            components.append(f"{RED}ctx:{remaining_int}%{RESET}")
        elif remaining_int < 50:
            components.append(f"{YELLOW}ctx:{remaining_int}%{RESET}")

    # Vim mode
    if vim_mode:
        color = GREEN if vim_mode == "INSERT" else MAGENTA
        components.append(f"{color}{vim_mode}{RESET}")

    # Join with separator
    separator = f" {DIM}|{RESET} "
    print(separator.join(components))


if __name__ == "__main__":
    main()

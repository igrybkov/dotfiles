#!/usr/bin/env python3
"""
Cursor Stop Hook: Set Zellij pane title based on chat content.

This hook runs when the Cursor agent finishes responding (stop event).
It generates a descriptive title from the first user message and sets
the Zellij pane title using `hive zellij set-title`.

The hook uses a marker file to track which sessions have been titled,
preventing duplicate title generation on subsequent stops.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


def get_first_user_message(transcript_path: str) -> Optional[str]:
    """Extract the first user message from a Cursor transcript.

    Cursor transcripts are plain text with format:
    user:
    <user_query>
    ...message...
    </user_query>
    """
    try:
        with open(transcript_path, "r") as f:
            content = f.read()

        # Find the first <user_query> block
        match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", content, re.DOTALL)
        if match:
            message = match.group(1).strip()
            # Skip if it looks like a system command
            if message.startswith("/") or message.startswith("<"):
                return None
            return message

        return None
    except Exception:
        return None


def get_marker_dir(conversation_id: str) -> Path:
    """Get the directory for storing marker files."""
    marker_dir = Path.home() / ".cursor" / "hook-state" / conversation_id
    marker_dir.mkdir(parents=True, exist_ok=True)
    return marker_dir


def is_already_titled(marker_dir: Path) -> bool:
    """Check if session has already been titled."""
    marker = marker_dir / ".zellij-titled"
    return marker.exists()


def mark_as_titled(marker_dir: Path) -> None:
    """Create marker file to prevent duplicate title generation."""
    marker = marker_dir / ".zellij-titled"
    marker.touch()


def generate_title(user_message: str) -> Optional[str]:
    """Generate a session title using Codex CLI."""
    import tempfile

    # Truncate long messages to avoid excessive API usage
    truncated = user_message[:1000] if len(user_message) > 1000 else user_message

    prompt = f"""Generate a short, descriptive title (3-6 words) for a coding session that started with this message:

"{truncated}"

Requirements:
- Title should summarize the main task or topic
- Use lowercase with hyphens (kebab-case), e.g., "refactor-auth-module"
- No quotes, no explanation, just the title itself
- If the message is unclear, use "general-coding-session"

Title:"""

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            output_file = f.name

        result = subprocess.run(
            [
                "codex",
                "exec",
                "--skip-git-repo-check",
                "-o",
                output_file,
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/tmp",
        )

        if result.returncode != 0:
            return None

        with open(output_file, "r") as f:
            title = f.read().strip()

        Path(output_file).unlink(missing_ok=True)

        # Clean up the title
        title = title.strip("\"'")
        title = title.lower()
        # Remove any non-alphanumeric chars except hyphens
        title = "".join(c if c.isalnum() or c == "-" else "-" for c in title)
        # Collapse multiple hyphens
        while "--" in title:
            title = title.replace("--", "-")
        title = title.strip("-")

        # Ensure reasonable length
        if len(title) < 3:
            return "coding-session"
        if len(title) > 50:
            title = title[:50].rsplit("-", 1)[0]

        return title

    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def set_zellij_title(title: str) -> bool:
    """Set the Zellij pane title using hive CLI."""
    # Only run if inside Zellij
    if not os.environ.get("ZELLIJ_SESSION_NAME"):
        return False

    try:
        result = subprocess.run(
            ["hive", "zellij", "set-title", "--title", title],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        sys.exit(0)

    # Extract fields - Cursor uses conversation_id, not session_id
    conversation_id = input_data.get("conversation_id", "")
    transcript_path = input_data.get("transcript_path", "")

    # Validate required fields
    if not conversation_id or not transcript_path:
        print(json.dumps({}))
        sys.exit(0)

    # Expand ~ in path
    transcript_path = os.path.expanduser(transcript_path)

    # Check if transcript exists
    if not os.path.exists(transcript_path):
        print(json.dumps({}))
        sys.exit(0)

    # Get marker directory
    marker_dir = get_marker_dir(conversation_id)

    # Check if already titled
    if is_already_titled(marker_dir):
        print(json.dumps({}))
        sys.exit(0)

    # Get first user message
    user_message = get_first_user_message(transcript_path)
    if not user_message:
        # No valid user message found, mark as titled to avoid retrying
        mark_as_titled(marker_dir)
        print(json.dumps({}))
        sys.exit(0)

    # Generate title
    title = generate_title(user_message)
    if not title:
        # Failed to generate, mark to avoid retrying
        mark_as_titled(marker_dir)
        print(json.dumps({}))
        sys.exit(0)

    # Set Zellij title
    if set_zellij_title(title):
        mark_as_titled(marker_dir)

    # Always allow agent to stop
    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()

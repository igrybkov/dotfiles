#!/usr/bin/env python3
"""
Claude Code Stop Hook: Auto-rename untitled sessions.

This hook runs when Claude Code finishes responding (Stop event).
It generates a descriptive title for untitled sessions using Claude Haiku
and renames them automatically.

The hook uses a marker file to track which sessions have been renamed,
preventing duplicate renames on subsequent stops.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def get_first_user_message(transcript_path: str) -> str | None:
    """Extract the first real user message from the transcript."""
    try:
        with open(transcript_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Skip non-user messages
                if entry.get("type") != "user":
                    continue

                # Skip meta messages (isMeta flag)
                if entry.get("isMeta"):
                    continue

                message = entry.get("message", {})

                # Skip if not a user role message
                if message.get("role") != "user":
                    continue

                content = message.get("content", "")

                # Handle string content
                if isinstance(content, str):
                    # Skip system-injected messages
                    if content.startswith("<local-command"):
                        continue
                    if content.startswith("<command-name>"):
                        continue
                    if content.strip():
                        return content.strip()

                # Handle array content (text blocks)
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()
                            if text and not text.startswith("<"):
                                return text

        return None
    except Exception:
        return None


def get_session_dir(transcript_path: str, session_id: str) -> Path:
    """Get the session directory for storing marker files."""
    # Transcript is at ~/.claude/projects/{project}/{session_id}.jsonl
    # Session dir is at ~/.claude/projects/{project}/{session_id}/
    transcript = Path(transcript_path)
    session_dir = transcript.parent / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def is_already_renamed(session_dir: Path) -> bool:
    """Check if session has already been renamed."""
    marker = session_dir / ".auto-renamed"
    return marker.exists()


def mark_as_renamed(session_dir: Path) -> None:
    """Create marker file to prevent duplicate renames."""
    marker = session_dir / ".auto-renamed"
    marker.touch()


def generate_title(user_message: str) -> str | None:
    """Generate a session title using Claude Haiku."""
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
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence", prompt],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return None

        title = result.stdout.strip()

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


def rename_session(transcript_path: str, session_id: str, title: str) -> bool:
    """Rename the session by updating sessions-index.json directly."""
    try:
        # sessions-index.json is in the same directory as the transcript
        project_dir = Path(transcript_path).parent
        index_path = project_dir / "sessions-index.json"

        if not index_path.exists():
            return False

        with open(index_path, "r") as f:
            index_data = json.load(f)

        # Find and update the session entry
        updated = False
        for entry in index_data.get("entries", []):
            if entry.get("sessionId") == session_id:
                entry["summary"] = title
                updated = True
                break

        if not updated:
            return False

        # Write back atomically
        tmp_path = index_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(index_data, f, indent=2)
        tmp_path.rename(index_path)

        return True
    except Exception:
        return False


def main():
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Invalid input, allow Claude to stop
        print(json.dumps({}))
        sys.exit(0)

    # Extract fields
    session_id = input_data.get("session_id", "")
    transcript_path = input_data.get("transcript_path", "")
    stop_hook_active = input_data.get("stop_hook_active", False)

    # Prevent infinite loops
    if stop_hook_active:
        print(json.dumps({}))
        sys.exit(0)

    # Validate required fields
    if not session_id or not transcript_path:
        print(json.dumps({}))
        sys.exit(0)

    # Expand ~ in path
    transcript_path = os.path.expanduser(transcript_path)

    # Check if transcript exists
    if not os.path.exists(transcript_path):
        print(json.dumps({}))
        sys.exit(0)

    # Get session directory
    session_dir = get_session_dir(transcript_path, session_id)

    # Check if already renamed
    if is_already_renamed(session_dir):
        print(json.dumps({}))
        sys.exit(0)

    # Get first user message
    user_message = get_first_user_message(transcript_path)
    if not user_message:
        # No valid user message found, mark as renamed to avoid retrying
        mark_as_renamed(session_dir)
        print(json.dumps({}))
        sys.exit(0)

    # Generate title
    title = generate_title(user_message)
    if not title:
        # Failed to generate, mark to avoid retrying
        mark_as_renamed(session_dir)
        print(json.dumps({}))
        sys.exit(0)

    # Rename session
    if rename_session(transcript_path, session_id, title):
        mark_as_renamed(session_dir)

    # Always allow Claude to stop
    print(json.dumps({}))
    sys.exit(0)


if __name__ == "__main__":
    main()

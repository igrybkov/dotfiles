"""
Ansible filter plugin for resolving GitHub SSH signing keys.

Usage in templates:
    {{ allowed_signers | resolve_github_signing_keys }}

The filter looks for entries with a 'github_user' field, fetches their SSH signing
keys from the GitHub API, and expands each entry into one entry per key.
Entries with a 'key' field (and no 'github_user') pass through unchanged.

Resolution strategy:
    1. Try gh CLI (handles authentication, GitHub Enterprise hosts)
    2. Fall back to direct HTTPS API call (works for public profiles without auth)

Requirements (at least one of):
    - gh CLI installed and authenticated: gh auth login
    - Network access to the GitHub API (public profiles only for HTTPS fallback)

Examples:
    # Input
    git_allowed_signers:
      - email: user@example.com
        github_user: octocat
      - email: other@example.com
        key: "ssh-ed25519 AAAA..."

    # Output (after | resolve_github_signing_keys)
    git_allowed_signers:
      - email: user@example.com
        key: "ssh-ed25519 AAAA..."  # fetched from GitHub
      - email: other@example.com
        key: "ssh-ed25519 AAAA..."  # passed through unchanged
"""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from ansible.utils.display import Display

display = Display()


class FilterModule:
    """Ansible filter plugin for GitHub SSH signing key resolution."""

    def filters(self) -> dict[str, Any]:
        return {
            "resolve_github_signing_keys": self.resolve_github_signing_keys,
        }

    def resolve_github_signing_keys(self, entries: list[dict]) -> list[dict]:
        """
        Resolve github_user entries into actual SSH signing keys.

        Entries with 'github_user' are expanded by fetching signing keys from
        the GitHub API. Entries with only 'key' pass through unchanged.

        Args:
            entries: List of allowed_signers entry dicts

        Returns:
            Expanded list with github_user entries replaced by concrete key entries
        """
        github_entries = [e for e in entries if "github_user" in e]
        if not github_entries:
            return entries

        has_gh = bool(shutil.which("gh"))

        result = []
        for entry in entries:
            if "github_user" not in entry:
                result.append(entry)
                continue

            username = entry["github_user"]
            hostname = entry.get("github_host", "github.com")
            keys = _fetch_signing_keys(username, hostname, has_gh)

            if not keys:
                display.warning(
                    f"No SSH signing keys found for GitHub user '{username}' "
                    f"on {hostname} — skipping"
                )
                continue

            for key in keys:
                new_entry = {
                    k: v
                    for k, v in entry.items()
                    if k not in ("github_user", "github_host")
                }
                new_entry["key"] = key
                result.append(new_entry)

        return result


@lru_cache(maxsize=64)
def _fetch_signing_keys(username: str, hostname: str, has_gh: bool) -> tuple[str, ...]:
    """
    Fetch SSH signing keys for a GitHub user.

    Tries gh CLI first, falls back to direct HTTPS API call.
    Returns a tuple of key strings (tuple for lru_cache hashability).
    """
    if has_gh:
        keys = _fetch_via_gh(username, hostname)
        if keys is not None:
            return keys
        display.v(
            f"gh CLI failed for '{username}' on {hostname}, falling back to HTTPS API"
        )

    return _fetch_via_https(username, hostname)


def _fetch_via_gh(username: str, hostname: str) -> tuple[str, ...] | None:
    """Fetch signing keys using the gh CLI. Returns None on failure."""
    try:
        result = subprocess.run(
            [
                "gh",
                "api",
                "--hostname",
                hostname,
                f"/users/{username}/ssh_signing_keys",
                "--jq",
                ".[].key",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            display.v(
                f"gh api failed for '{username}' on {hostname}: {result.stderr.strip()}"
            )
            return None

        keys = [
            line.strip() for line in result.stdout.strip().splitlines() if line.strip()
        ]
        return tuple(keys)

    except subprocess.TimeoutExpired:
        display.v(f"gh api timed out for '{username}' on {hostname}")
        return None
    except OSError as e:
        display.v(f"Error running gh CLI: {e}")
        return None


def _fetch_via_https(username: str, hostname: str) -> tuple[str, ...]:
    """Fetch signing keys via direct HTTPS API call (no auth, public profiles only)."""
    url = f"https://{hostname}/api/v3/users/{username}/ssh_signing_keys"
    if hostname == "github.com":
        url = f"https://api.github.com/users/{username}/ssh_signing_keys"

    try:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode())

        keys = [entry["key"] for entry in data if "key" in entry]
        return tuple(keys)

    except (URLError, json.JSONDecodeError, KeyError, OSError) as e:
        display.warning(
            f"HTTPS API fallback failed for '{username}' on {hostname}: {e}"
        )
        return ()

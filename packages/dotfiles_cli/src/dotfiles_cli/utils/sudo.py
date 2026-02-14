"""Sudo password validation utilities."""

from __future__ import annotations

import subprocess


def validate_sudo_password(password: str) -> bool:
    """Validate that the given password is correct for sudo.

    Uses `sudo -S -v` to validate the password without running any command.
    The -S flag reads password from stdin, -v updates the cached credentials.

    Args:
        password: The sudo password to validate

    Returns:
        True if the password is valid, False otherwise
    """
    try:
        result = subprocess.run(
            ["sudo", "-S", "-v"],
            input=password + "\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

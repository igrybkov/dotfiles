"""Ansible vault client-script protocol entrypoint.

Ansible detects this as a vault client because the script name ends in
`-client`. It invokes us with `--vault-id LABEL` and expects the password
on stdout. See https://docs.ansible.com/ansible-core/devel/vault_guide/vault_managing_passwords.html

Exit codes:
    0 — password printed on stdout
    2 — label not found in the backend (Ansible will fall through to the
        next `--vault-id` source, or error)
    3 — backend not ready (e.g. gpg not installed on Linux)

No logging on success — only the password on stdout.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .backend import get_backend
from .backends import onepassword


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dotfiles-vault-client",
        description="Ansible vault password client for dotfiles.",
        add_help=True,
    )
    # Ansible passes --vault-id LABEL; default to "common" for standalone use.
    parser.add_argument(
        "--vault-id",
        dest="vault_id",
        default="common",
        help="Vault identity label (default: 'common').",
    )
    args = parser.parse_args(argv)
    label = args.vault_id or "common"

    try:
        backend = get_backend()
    except Exception as exc:  # pragma: no cover — guard only
        print(
            f"dotfiles-vault-client: failed to initialize backend: {exc}",
            file=sys.stderr,
        )
        return 3

    try:
        password = backend.read(label)
    except Exception as exc:
        # Backend surfaced an error we can't recover from (gpg not installed,
        # wrong master password, corrupted keychain, etc.). Surface it with
        # actionable guidance.
        print(
            f"dotfiles-vault-client: backend error reading {label!r}: {exc}",
            file=sys.stderr,
        )
        print(
            "Run `dotfiles secret keychain status` to diagnose, or "
            "`dotfiles secret init` to set up.",
            file=sys.stderr,
        )
        return 3

    if password is None:
        # Try 1Password fallback before giving up.
        password = onepassword.read_field(label)
        if password is not None:
            # Write-through so the next run doesn't need 1Password.
            try:
                backend.write(label, password)
            except Exception:
                # Non-fatal: we still have the password in hand for this run.
                pass

    if password is None:
        print(
            f"dotfiles-vault-client: no password stored for label {label!r}.",
            file=sys.stderr,
        )
        print(
            f"Run `dotfiles secret keychain push {label}` to register one.",
            file=sys.stderr,
        )
        return 2

    # Ansible vault client script protocol: password + newline on stdout.
    sys.stdout.write(password)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover — invoked as a script
    sys.exit(main())

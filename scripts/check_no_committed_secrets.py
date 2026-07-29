#!/usr/bin/env python3
"""Fail if any git-tracked file looks like an encrypted secret.

Encrypted secrets belong only in private profiles (gitignored, each its own
repo). The public dotfiles repo must never track one. This hook enforces that
by scanning ``git ls-files`` and rejecting any tracked file that is:

1. named ``secrets.yml``, or located under a directory named ``secrets/``
   (the convention the vault_secret lookup itself uses), OR
2. Ansible-Vault-encrypted (starts with ``$ANSIBLE_VAULT``), OR
3. sops-encrypted (YAML with a top-level ``sops:`` mapping — detected with the
   same ``dotfiles_cli.vault.sops.is_sops_encrypted`` the CLI uses, so the two
   definitions never drift).

It runs its own ``git ls-files`` scan, so wire it up with
``pass_filenames: false``. It must NOT flag source/docs/tests that merely
mention these markers as text — only files that are named, located, or
structured as an actual secret.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# dotfiles_cli is importable in the mise/uv venv this hook runs under.
from dotfiles_cli.vault.sops import is_sops_encrypted

VAULT_HEADER = b"$ANSIBLE_VAULT"


def tracked_files(repo_root: Path) -> list[Path]:
    """Return every git-tracked path (relative to the repo root)."""
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [Path(p) for p in out.split("\0") if p]


def has_secret_name_or_location(rel_path: Path) -> bool:
    """True if the path is named ``secrets.yml`` or sits under a ``secrets/`` dir."""
    if rel_path.name == "secrets.yml":
        return True
    return "secrets" in rel_path.parts[:-1]


def is_ansible_vault_encrypted(path: Path) -> bool:
    """True if the file begins with the Ansible-Vault header (binary-safe)."""
    try:
        with open(path, "rb") as fh:
            return fh.read(len(VAULT_HEADER)) == VAULT_HEADER
    except OSError:
        return False


def is_sops_encrypted_safe(path: Path) -> bool:
    """``is_sops_encrypted`` guarded against binary/undecodable tracked files.

    ``is_sops_encrypted`` reads the file as text, which raises on binary blobs
    (fonts, images). Those are obviously not sops files, so swallow any failure.
    """
    try:
        return is_sops_encrypted(path)
    except Exception:
        return False


def find_offenders(repo_root: Path) -> list[tuple[Path, str]]:
    offenders: list[tuple[Path, str]] = []
    for rel in tracked_files(repo_root):
        abs_path = repo_root / rel
        if not abs_path.is_file():
            continue
        if has_secret_name_or_location(rel):
            offenders.append(
                (rel, "named 'secrets.yml' or under a 'secrets/' directory")
            )
        elif is_ansible_vault_encrypted(abs_path):
            offenders.append((rel, "Ansible-Vault-encrypted ($ANSIBLE_VAULT)"))
        elif is_sops_encrypted_safe(abs_path):
            offenders.append((rel, "sops-encrypted (top-level 'sops:' mapping)"))
    return offenders


def main() -> int:
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )

    offenders = find_offenders(repo_root)
    if not offenders:
        return 0

    print(
        "ERROR: encrypted secret(s) are tracked in the public repo. "
        "Secrets belong only in private profiles (gitignored, separate repos).",
        file=sys.stderr,
    )
    for rel, reason in offenders:
        print(f"  - {rel}: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

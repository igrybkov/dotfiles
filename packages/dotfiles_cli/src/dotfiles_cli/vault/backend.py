"""Vault backend protocol and platform-specific selector.

Two backends, selected by platform:

- macOS: dedicated keychain file with per-item ACL (`security` CLI).
- Anywhere else (Linux / WSL / containers): GPG-symmetric-encrypted file
  unlocked by a single master password (`gpg` CLI).

Both backends store per-vault-id passwords keyed by label. The `label`
matches the Ansible `--vault-id` label and, in this repo, equals the
profile name (or `common` for the shared default).
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable


@runtime_checkable
class VaultBackend(Protocol):
    """Persistent storage for per-vault-id passwords."""

    def ensure_ready(self) -> None:
        """Idempotently set up whatever the backend needs to operate.

        For macOS: create the dedicated keychain + unlock chain if absent.
        For GPG: verify gpg is installed and the config dir exists.
        Safe to call repeatedly; a no-op when everything is in place.
        """

    def read(self, label: str) -> str | None:
        """Return the stored password for `label`, or None if absent.

        Must not prompt the user directly — prompting happens in CLI wrappers
        before any Ansible invocation, so vault-client runs never block on
        missing TTYs.
        """

    def write(self, label: str, password: str) -> None:
        """Persist `password` under `label`, replacing any prior value."""

    def delete(self, label: str) -> None:
        """Remove the stored password for `label`. No-op if absent."""

    def list_labels(self) -> list[str]:
        """Return all labels with a stored password, sorted."""

    def status(self) -> dict:
        """Return a diagnostic snapshot for `dotfiles secret keychain status`.

        Must not include password values — keys only.
        """


_backend: VaultBackend | None = None


def get_backend() -> VaultBackend:
    """Return the platform-appropriate backend, memoized for the process.

    macOS → MacOSDedicatedKeychain; everything else → GpgFileBackend.
    No env-var override in v1 — the platform split is opinionated.
    """
    global _backend
    if _backend is not None:
        return _backend

    if sys.platform == "darwin":
        from .backends.macos import MacOSKeyringBackend

        _backend = MacOSKeyringBackend()
    else:
        from .backends.gpg_file import GpgFileBackend

        _backend = GpgFileBackend()
    return _backend


def reset_backend_cache() -> None:
    """Clear the memoized backend. Test-only helper."""
    global _backend
    _backend = None

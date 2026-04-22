"""macOS vault backend — thin wrapper over `keyring`.

Stores each vault-id password as a generic-password item in the user's
**login keychain** under the service name `com.grybkov.dotfiles.vault`.
Item locking follows the user's login keychain lock policy (unlocked at
login, locked on sleep / screensaver when the Screen Lock setting
requires password).

The backend uses the Python `keyring` library, which calls Security
framework APIs directly. The Python interpreter becomes the ACL-trusted
creator on first write; later reads from the same interpreter succeed
without prompting. After a `uv sync --upgrade` bumps the Python version,
the interpreter's code signature changes — macOS may then prompt once
and offer "Always Allow" to bind the new interpreter to the ACL.

Label names are tracked in a plain JSON file so listing doesn't need to
touch the keychain (and isn't ACL-gated). Label names aren't secrets —
`security dump-keychain` lists them anyway.
"""

from __future__ import annotations

import json
from pathlib import Path

import keyring
import keyring.errors

from ..backend import VaultBackend  # noqa: F401 (for IDE/type-check)
from ...constants import (
    VAULT_KEYCHAIN_SERVICE,
    get_macos_labels_file,
)


class MacOSKeyringBackend:
    """Login-keychain-backed vault backend via `keyring`."""

    def __init__(
        self,
        service: str = VAULT_KEYCHAIN_SERVICE,
        labels_path: Path | None = None,
    ) -> None:
        self.service = service
        self.labels_path = labels_path or get_macos_labels_file()

    def ensure_ready(self) -> None:
        """No-op: login keychain always exists and the JSON file is created on first write."""

    def read(self, label: str) -> str | None:
        try:
            return keyring.get_password(self.service, label)
        except keyring.errors.KeyringError:
            return None

    def write(self, label: str, password: str) -> None:
        keyring.set_password(self.service, label, password)
        self._update_labels(add=label)

    def delete(self, label: str) -> None:
        try:
            keyring.delete_password(self.service, label)
        except keyring.errors.PasswordDeleteError:
            # Already gone — idempotent.
            pass
        self._update_labels(remove=label)

    def list_labels(self) -> list[str]:
        if not self.labels_path.exists():
            return []
        try:
            data = json.loads(self.labels_path.read_text())
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        return sorted(str(x) for x in data if isinstance(x, str))

    def status(self) -> dict:
        return {
            "backend": "macos-login-keychain",
            "service": self.service,
            "labels": self.list_labels(),
            "labels_path": str(self.labels_path),
            "keyring_backend": type(keyring.get_keyring()).__name__,
        }

    def _update_labels(
        self, *, add: str | None = None, remove: str | None = None
    ) -> None:
        labels = set(self.list_labels())
        if add:
            labels.add(add)
        if remove:
            labels.discard(remove)
        self.labels_path.parent.mkdir(parents=True, exist_ok=True)
        self.labels_path.write_text(json.dumps(sorted(labels)))
        self.labels_path.chmod(0o600)

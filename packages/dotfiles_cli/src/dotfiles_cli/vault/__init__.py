"""Vault and secrets management for the dotfiles CLI.

Secrets are stored with sops+age (``sops``, ``age`` submodules), fronted by the
``dotfiles secret`` commands. The legacy Ansible-Vault decrypt path survives
only inside the ``vault_secret`` lookup plugin, for reading historical
vault-encrypted files a colleague may still have; the CLI-side machinery for
*managing* vault passwords has been removed.

``get_backend`` remains the storage abstraction for this machine's age key
(macOS login keychain, or a GPG-encrypted file elsewhere).
"""

from .backend import VaultBackend, get_backend, reset_backend_cache
from . import sops
from .age import (
    AGE_KEY_LABEL,
    OP_ITEM_TITLE,
    delete_age_key,
    generate_keypair,
    get_public_key_from_private,
    is_age_keygen_available,
    is_op_available,
    is_sops_available,
    read_age_key,
    read_age_key_from_op,
    read_age_key_via_subprocess,
    resolve_sops,
    write_age_key,
    write_age_key_to_op,
)

__all__ = [
    # Backend abstraction (age key storage)
    "VaultBackend",
    "get_backend",
    "reset_backend_cache",
    # sops module (sops.decrypt_all, sops.encrypt_file, ...)
    "sops",
    # age identity management
    "AGE_KEY_LABEL",
    "OP_ITEM_TITLE",
    "delete_age_key",
    "generate_keypair",
    "get_public_key_from_private",
    "is_age_keygen_available",
    "is_op_available",
    "is_sops_available",
    "read_age_key",
    "read_age_key_from_op",
    "read_age_key_via_subprocess",
    "resolve_sops",
    "write_age_key",
    "write_age_key_to_op",
]

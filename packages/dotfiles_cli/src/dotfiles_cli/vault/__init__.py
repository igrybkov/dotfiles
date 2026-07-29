"""Vault and secrets management for the dotfiles CLI.

During the Ansible-Vault -> sops migration both backends coexist:

- The Ansible-Vault path (``operations``, ``password``) still backs the
  ``mcp-servers`` Ansible role and any profile not yet migrated.
- The sops path (``sops``, ``age``) is the new secret store, fronted by the
  ``dotfiles secret`` commands.

Both surfaces are re-exported here. sops/age helpers keep their module-name
spelling (``sops_*`` / age functions) so they don't collide with the
Ansible-Vault ``get_profiles_with_secrets`` that ``install`` still imports.
"""

from .backend import VaultBackend, get_backend, reset_backend_cache
from .password import (
    get_vault_password,
    get_vault_password_file,
    get_vault_id,
    ensure_vault_password_permissions,
    write_vault_password_file,
    validate_vault_password,
)
from .operations import (
    run_ansible_vault,
    get_secrets_file,
    get_all_secret_locations,
    get_profiles_with_secrets,
)
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
    resolve_sops,
    write_age_key,
    write_age_key_to_op,
)

__all__ = [
    # Backend abstraction
    "VaultBackend",
    "get_backend",
    "reset_backend_cache",
    # Password management (Ansible Vault)
    "get_vault_password",
    "get_vault_password_file",
    "get_vault_id",
    "ensure_vault_password_permissions",
    "write_vault_password_file",
    "validate_vault_password",
    # Operations (Ansible Vault)
    "run_ansible_vault",
    "get_secrets_file",
    "get_all_secret_locations",
    "get_profiles_with_secrets",
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
    "resolve_sops",
    "write_age_key",
    "write_age_key_to_op",
]

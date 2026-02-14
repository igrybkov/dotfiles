"""Vault and secrets management for the dotfiles CLI."""

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

__all__ = [
    # Password management
    "get_vault_password",
    "get_vault_password_file",
    "get_vault_id",
    "ensure_vault_password_permissions",
    "write_vault_password_file",
    "validate_vault_password",
    # Operations
    "run_ansible_vault",
    "get_secrets_file",
    "get_all_secret_locations",
    "get_profiles_with_secrets",
]

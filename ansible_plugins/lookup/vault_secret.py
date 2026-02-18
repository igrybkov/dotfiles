"""
Ansible lookup plugin for reading secrets from vault-encrypted files.

Usage in templates:
    {{ lookup('vault_secret', 'mcp_secrets.habitify.api_key') }}

Usage in variables:
    env:
      API_KEY: "{{ lookup('vault_secret', 'mcp_secrets.habitify.api_key') }}"

The plugin searches for secrets in:
    1. secrets/<inventory_hostname>.yml
    2. secrets/common.yml
    3. profiles/<profile>/secrets.yml (using shared discovery for multi-level profiles)
    4. profiles/<profile>/secrets/*.yml
    5. profiles/common/secrets.yml
    6. profiles/common/secrets/*.yml
"""

from __future__ import annotations

import getpass
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

# Add the shared package to Python path for Ansible plugin usage
# (Ansible plugins can't use pip dependencies directly)
_packages_dir = Path(__file__).parent.parent.parent / "packages"
_discovery_pkg = _packages_dir / "dotfiles_profile_discovery" / "src"
if str(_discovery_pkg) not in sys.path:
    sys.path.insert(0, str(_discovery_pkg))

import yaml  # noqa: E402
from ansible.errors import AnsibleError  # noqa: E402
from ansible.plugins.lookup import LookupBase  # noqa: E402
from ansible.parsing.vault import VaultLib, VaultSecret  # noqa: E402
from ansible.parsing.dataloader import DataLoader  # noqa: E402
from dotfiles_profile_discovery import get_profile_by_name  # noqa: E402

# Module-level cache for vault password (to avoid prompting multiple times)
_vault_password_cache: bytes | None = None


class LookupModule(LookupBase):
    def run(
        self, terms: list[str], variables: dict | None = None, **kwargs
    ) -> list[Any]:
        results = []

        # Get playbook directory from variables
        playbook_dir = (
            variables.get("playbook_dir", os.getcwd()) if variables else os.getcwd()
        )
        secrets_dir = Path(playbook_dir) / "secrets"

        # Determine which vault files to check
        inventory_hostname = (
            variables.get("inventory_hostname", "common") if variables else "common"
        )

        # Support _vault_profile override for aggregated runs where secrets
        # need to be resolved from a specific profile rather than current host
        vault_profile = variables.get("_vault_profile") if variables else None

        # Build list of potential vault files to check
        # Priority: profile-specific secrets, then common secrets
        if vault_profile:
            current_profile = vault_profile
        else:
            current_profile = inventory_hostname.replace("-profile", "")

        vault_files = [
            secrets_dir / f"{inventory_hostname}.yml",
            secrets_dir / "common.yml",
        ]

        # Also check profile secrets (both secrets.yml in profile root and secrets/*.yml)
        # Uses shared discovery for multi-level profile support (e.g., 'myrepo-work' -> 'profiles/myrepo/work/')
        profiles_dir = Path(playbook_dir) / "profiles"
        if profiles_dir.exists():
            for profile_name in [current_profile, "common"]:
                # Use shared discovery to get actual profile path (supports multi-level profiles)
                profile_info = get_profile_by_name(profiles_dir, profile_name)
                if profile_info is not None:
                    profile_dir = profile_info.path
                    # Check secrets.yml directly in profile directory (documented structure)
                    profile_secrets_file = profile_dir / "secrets.yml"
                    if (
                        profile_secrets_file.exists()
                        and profile_secrets_file not in vault_files
                    ):
                        vault_files.append(profile_secrets_file)

                    # Also check secrets/ subdirectory for multiple secrets files
                    profile_secrets_dir = profile_dir / "secrets"
                    if profile_secrets_dir.exists():
                        for secret_file in sorted(profile_secrets_dir.glob("*.yml")):
                            if secret_file not in vault_files:
                                vault_files.append(secret_file)

        # Try to use Ansible's loader to decrypt vault files (uses --vault-password-file automatically)
        # This is the preferred method as it integrates with Ansible's vault password mechanism
        loader = None

        # Try to get loader from self (if available from Ansible context)
        if hasattr(self, "_loader") and self._loader is not None:
            loader = self._loader
        else:
            # Create a new loader and try to get vault password from it
            loader = DataLoader()
            # Try to set up vault secrets from environment or file
            vault_password = self._get_vault_password(playbook_dir)
            if vault_password:
                loader.set_vault_secrets([(None, VaultSecret(vault_password))])

        # Load all available vault files
        all_secrets = []
        for vault_file in vault_files:
            if vault_file.exists():
                try:
                    data = loader.load_from_file(str(vault_file))
                    if data:
                        all_secrets.append(data)
                except Exception:
                    vault_password = self._get_vault_password(playbook_dir)
                    data = self._load_vault_file(vault_file, vault_password)
                    if data:
                        all_secrets.append(data)

        if not all_secrets:
            checked_locations = [str(f) for f in vault_files if f.parent.exists()]
            raise AnsibleError(
                "No vault secrets file found. Checked locations:\n"
                + "\n".join(f"  - {loc}" for loc in checked_locations)
            )

        # Resolve each term by searching across all loaded vault files
        for term in terms:
            value = None
            for secrets in all_secrets:
                value = self._resolve_path(secrets, term)
                if value is not None:
                    break
            if value is None:
                raise AnsibleError(f"Secret not found: {term}")
            results.append(value)

        return results

    def _get_vault_password(self, playbook_dir: str) -> bytes:
        """Get vault password from file, environment, or prompt interactively."""
        global _vault_password_cache

        # Return cached password if available
        if _vault_password_cache is not None:
            return _vault_password_cache

        # Try .vault_password file in multiple locations
        # 1. In playbook_dir (where ansible-playbook is run from)
        # 2. In current working directory
        # 3. In parent directories (up to 3 levels up from playbook_dir)
        vault_pass_locations = [
            Path(playbook_dir) / ".vault_password",
            Path.cwd() / ".vault_password",
        ]

        # Also check parent directories of playbook_dir (in case playbook_dir is a subdirectory)
        playbook_path = Path(playbook_dir)
        for _ in range(3):
            playbook_path = playbook_path.parent
            vault_pass_locations.append(playbook_path / ".vault_password")

        for vault_pass_file in vault_pass_locations:
            if vault_pass_file.exists() and vault_pass_file.is_file():
                try:
                    _vault_password_cache = vault_pass_file.read_text().strip().encode()
                    return _vault_password_cache
                except (OSError, IOError, PermissionError):
                    # File exists but can't read it, try next location
                    continue

        # Try environment variable
        env_password = os.environ.get("ANSIBLE_VAULT_PASSWORD")
        if env_password:
            _vault_password_cache = env_password.encode()
            return _vault_password_cache

        # Try loading OP_SECRET from .env file
        dotenv_file = Path(playbook_dir) / ".env"
        if dotenv_file.exists():
            from dotenv import load_dotenv

            load_dotenv(dotenv_file, override=False)

        # Try 1Password via OP_SECRET environment variable
        op_secret = os.environ.get("OP_SECRET")
        if op_secret:
            try:
                import subprocess

                result = subprocess.run(
                    ["op", "read", "-n", op_secret],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                _vault_password_cache = result.stdout.strip().encode()
                return _vault_password_cache
            except subprocess.CalledProcessError as e:
                raise AnsibleError(f"Failed to read secret from 1Password: {e.stderr}")
            except FileNotFoundError:
                raise AnsibleError(
                    "OP_SECRET is set but 'op' CLI is not installed. "
                    "Install it with: brew install 1password-cli"
                )

        # Try to get vault password from Ansible's loader if available
        # This works when --vault-password-file is passed to ansible-playbook
        try:
            if hasattr(self, "_loader") and self._loader is not None:
                # Try to get vault secrets from loader
                vault_secrets = getattr(self._loader, "vault_secrets", None)
                if vault_secrets:
                    # vault_secrets is a list of tuples: [(vault_id, VaultSecret), ...]
                    for vault_id, vault_secret in vault_secrets:
                        if vault_secret is not None:
                            # Try to get the password from the vault secret
                            # VaultSecret has a .secret attribute that contains the password bytes
                            if hasattr(vault_secret, "secret"):
                                password_bytes = vault_secret.secret
                                if password_bytes:
                                    _vault_password_cache = password_bytes
                                    return _vault_password_cache
        except (AttributeError, TypeError):
            # Loader or vault_secrets not available, continue to next method
            pass

        # Prompt interactively - try multiple methods to get terminal access
        # When Ansible evaluates lookups, stdin might be redirected, but we can try /dev/tty
        try:
            # Display prompt using Ansible's display (goes to stdout/stderr, not stdin)
            if hasattr(self, "_display"):
                self._display.display("Vault password: ", screen_only=True)
            else:
                # Fallback: write directly to stderr (which is usually connected to terminal)
                sys.stderr.write("Vault password: ")
                sys.stderr.flush()

            password = None
            tty_path = "/dev/tty"

            # Method 1: Try getpass.getpass() - it internally tries /dev/tty first, then stdin
            # This is the preferred method as it hides the password
            try:
                password = getpass.getpass("")
            except (OSError, IOError, ValueError, EOFError) as e:
                # getpass failed - try reading from /dev/tty directly
                error_code = getattr(e, "errno", None)
                error_msg = str(e).lower()

                # Method 2: Try reading from /dev/tty directly with input() (will echo)
                if error_code in (5, 6, 25) or any(
                    phrase in error_msg
                    for phrase in [
                        "device not configured",
                        "bad file descriptor",
                        "closed",
                    ]
                ):
                    try:
                        if hasattr(self, "_display"):
                            self._display.warning(
                                "Terminal echo control not available. Password will be visible!"
                            )

                        # Try reading from /dev/tty directly
                        if os.path.exists(tty_path) and os.access(tty_path, os.R_OK):
                            # Redirect stdin to /dev/tty temporarily
                            original_stdin = sys.stdin
                            try:
                                tty_file = open(tty_path, "r")
                                sys.stdin = tty_file
                                try:
                                    password = input(
                                        "Vault password (will be visible): "
                                    )
                                finally:
                                    tty_file.close()
                                    sys.stdin = original_stdin
                            except (OSError, IOError, ValueError):
                                # /dev/tty method failed, restore stdin and try regular input()
                                sys.stdin = original_stdin
                                password = input("Vault password (will be visible): ")
                        else:
                            # No /dev/tty, try regular input() (might work if stdin is still connected)
                            password = input("Vault password (will be visible): ")
                    except (EOFError, OSError, IOError, ValueError, AttributeError):
                        # All methods failed
                        raise AnsibleError(
                            "Cannot prompt for vault password (no terminal available).\n"
                            "Lookups are evaluated during task parsing when stdin may be redirected.\n\n"
                            "Solutions:\n"
                            "  1. Create .vault_password file: dotfiles secret init\n"
                            "  2. Set environment variable: export ANSIBLE_VAULT_PASSWORD='your-password'\n"
                            "  3. Use 1Password: Set OP_SECRET to a secret reference (e.g., op://vault/item/password)\n"
                            "  4. Run ansible-playbook directly (not through wrapper) with --ask-vault-pass"
                        )
                else:
                    # Re-raise if it's not a terminal error (might be a different issue)
                    raise

            # Handle case where password is empty
            if not password:
                raise AnsibleError("Vault password cannot be empty.")

            # Cache the password for subsequent lookups
            _vault_password_cache = password.encode()
            return _vault_password_cache

        except (KeyboardInterrupt, EOFError):
            raise AnsibleError("Vault password prompt cancelled.")
        except AnsibleError:
            # Re-raise AnsibleError as-is
            raise
        except Exception as e:
            # Handle any other unexpected errors
            error_msg = str(e).lower()
            error_code = getattr(e, "errno", None)

            terminal_errors = [
                "closed",
                "bad file descriptor",
                "not available",
                "permission denied",
                "device not configured",
                "input/output error",
            ]

            if error_code in (5, 6, 25) or any(
                phrase in error_msg for phrase in terminal_errors
            ):
                raise AnsibleError(
                    "Cannot prompt for vault password (no terminal available).\n"
                    "Lookups are evaluated during task parsing when stdin may be redirected.\n\n"
                    "Solutions:\n"
                    "  1. Create .vault_password file: dotfiles secret init\n"
                    "  2. Set environment variable: export ANSIBLE_VAULT_PASSWORD='your-password'\n"
                    "  3. Use 1Password: Set OP_SECRET to a secret reference (e.g., op://vault/item/password)\n"
                    "  4. Run ansible-playbook directly (not through wrapper) with --ask-vault-pass"
                )
            raise AnsibleError(f"Failed to prompt for vault password: {e}")

    @lru_cache(maxsize=8)
    def _load_vault_file(self, vault_file: Path, vault_password: bytes) -> dict | None:
        """Load and decrypt a vault file."""
        try:
            vault = VaultLib(secrets=[(None, VaultSecret(vault_password))])
            encrypted_data = vault_file.read_bytes()

            # Check if file is encrypted
            if not encrypted_data.startswith(b"$ANSIBLE_VAULT"):
                # Not encrypted, just load as YAML
                return yaml.safe_load(encrypted_data)

            # Decrypt
            decrypted = vault.decrypt(encrypted_data)
            return yaml.safe_load(decrypted)
        except Exception as e:
            raise AnsibleError(f"Failed to decrypt {vault_file}: {e}")

    def _resolve_path(self, data: dict, path: str) -> Any:
        """Resolve a dot-notation path in the data dict."""
        parts = path.split(".")
        current = data

        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None

        return current

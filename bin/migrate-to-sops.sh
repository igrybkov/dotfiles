#!/usr/bin/env bash
# Migrate a profile's secrets.yml from Ansible Vault to sops + age.
#
# Usage:
#   bin/migrate-to-sops.sh <profile-name>
#
# Prerequisites (in this order):
#   1. Run `dotfiles secret init` first. This generates your age keypair,
#      stores the private key in the OS keychain, and writes the public key
#      into .sops.yaml. Commit .sops.yaml.
#   2. `ansible-vault`, `sops`, and `age` must be installed.
#   3. The profile's existing Ansible Vault password must still be reachable
#      (the old per-profile keychain label coexists with the new age key —
#      they use different labels, so you don't have to delete anything yet).
#
# What it does, for one profile:
#   - Locates profiles/<path>/secrets.yml (handles multi-level profiles).
#   - Verifies the file is currently Ansible-Vault-encrypted.
#   - Backs the original up to secrets.yml.vault.bak.
#   - Decrypts it with ansible-vault (via the dotfiles vault client).
#   - Writes the plaintext to the real secrets.yml path, then encrypts it
#     IN PLACE with sops (the .sops.yaml path_regex only matches the real
#     path, not a temp path, which is why we encrypt in place).
#   - On any failure, restores the original from the backup.
#
# AFTER migrating every profile and confirming `dotfiles secret get` works,
# remove the now-unused per-profile vault passwords from the keychain with
# `dotfiles secret keychain rm <profile>` (do this LAST, not before).

set -euo pipefail

if [[ $# -eq 0 ]]; then
  printf 'Usage: %s <profile-name>\n' "$0" >&2
  printf '       %s --all\n' "$0" >&2
  exit 1
fi

# --all: discover every profile with an Ansible-Vault-encrypted secrets.yml
# and migrate each one in turn.
if [[ "$1" == "--all" ]]; then
  PROFILES="$(
    cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.." && \
    mise x -- uv run python - <<'PY'
from dotfiles_cli.vault.operations import get_profiles_with_secrets
for p in get_profiles_with_secrets():
    print(p)
PY
  )"
  if [[ -z "$PROFILES" ]]; then
    printf 'No profiles with Ansible-Vault-encrypted secrets found.\n'
    exit 0
  fi
  failed=()
  while IFS= read -r profile; do
    printf '\n=== Migrating: %s ===\n' "$profile"
    if ! "$0" "$profile"; then
      failed+=("$profile")
    fi
  done <<< "$PROFILES"
  if [[ ${#failed[@]} -gt 0 ]]; then
    printf '\nFailed: %s\n' "${failed[*]}" >&2
    exit 1
  fi
  printf '\nAll profiles migrated.\n'
  exit 0
fi

PROFILE="$1"

# Resolve the repo root from this script's location (bin/..).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

err() { printf 'Error: %s\n' "$*" >&2; }

if ! command -v ansible-vault >/dev/null 2>&1; then
  err "ansible-vault not found on PATH. Install it before migrating."
  exit 1
fi
if ! mise x -- sops --version >/dev/null 2>&1; then
  err "sops not found. Run: mise install"
  exit 1
fi

# Resolve the secrets file path via the dotfiles CLI so multi-level profiles
# (e.g. 'myrepo-work' -> profiles/myrepo/work/secrets.yml) resolve correctly.
SECRETS_FILE="$(
  cd "${REPO_ROOT}" && mise x -- uv run python - "$PROFILE" <<'PY'
import sys
from dotfiles_cli.vault.sops import get_secrets_file
try:
    print(get_secrets_file(sys.argv[1]))
except Exception as exc:  # noqa: BLE001
    print(f"__ERR__ {exc}", file=sys.stderr)
    sys.exit(1)
PY
)" || { err "could not resolve secrets file for profile '${PROFILE}'"; exit 1; }

if [[ ! -f "${SECRETS_FILE}" ]]; then
  err "secrets file not found: ${SECRETS_FILE}"
  exit 1
fi

# shellcheck disable=SC2016  # literal '$ANSIBLE_VAULT' marker, no expansion wanted
if ! head -n 1 "${SECRETS_FILE}" | grep -qF '$ANSIBLE_VAULT'; then
  err "${SECRETS_FILE} is not Ansible-Vault-encrypted (already migrated?)."
  exit 1
fi

BACKUP="${SECRETS_FILE}.vault.bak"
cp -p "${SECRETS_FILE}" "${BACKUP}"
printf 'Backed up original to %s\n' "${BACKUP}"

# Short-lived plaintext for the decrypt buffer (mode 600, trap-cleaned).
TMP_PLAIN="$(mktemp -t dotfiles-sops-migrate.XXXXXX)"
chmod 600 "${TMP_PLAIN}"

restore() {
  err "migration failed; restoring original from backup."
  cp -p "${BACKUP}" "${SECRETS_FILE}"
}

cleanup() {
  rm -f "${TMP_PLAIN}"
}
trap cleanup EXIT

# 1. Decrypt with ansible-vault into the temp buffer.
# Use the dotfiles vault-client so the password is read from the OS keychain
# (same path the CLI uses) rather than prompting interactively.
VAULT_CLIENT="${SCRIPT_DIR}/dotfiles-vault-client"
if [[ ! -x "${VAULT_CLIENT}" ]]; then
  err "vault client not found: ${VAULT_CLIENT}"
  exit 1
fi
if ! mise x -- ansible-vault decrypt \
       --vault-id "${PROFILE}@${VAULT_CLIENT}" \
       --output "${TMP_PLAIN}" \
       "${SECRETS_FILE}"; then
  restore
  err "ansible-vault decrypt failed (is the password stored? run: dotfiles secret keychain status)"
  exit 1
fi

# 2. Write plaintext to the REAL path (so .sops.yaml path_regex matches),
#    then encrypt in place with sops.
cp "${TMP_PLAIN}" "${SECRETS_FILE}"
if ! mise x -- sops --encrypt --in-place "${SECRETS_FILE}"; then
  restore
  err "sops encrypt failed. Original restored; nothing lost."
  exit 1
fi

# 3. Sanity check: the file should now be sops-encrypted YAML.
if ! grep -q '^sops:' "${SECRETS_FILE}" && ! grep -q 'sops:' "${SECRETS_FILE}"; then
  restore
  err "post-encrypt sanity check failed (no sops metadata). Original restored."
  exit 1
fi

printf 'Migrated %s to sops.\n' "${SECRETS_FILE}"
printf 'Verify with: dotfiles secret list -p %s\n' "${PROFILE}"
printf 'When all profiles are migrated and verified, remove the old vault\n'
printf 'password with: dotfiles secret keychain rm %s\n' "${PROFILE}"
printf 'Then delete the backup: rm %s\n' "${BACKUP}"

#!/usr/bin/env bash
# Vault password helper script
# Returns password from various sources in order of priority:
# 1. ANSIBLE_VAULT_PASSWORD environment variable
# 2. .vault_password file
# 3. .env file (loads OP_SECRET)
# 4. OP_SECRET environment variable (1Password secret reference)
# (Interactive prompting is handled by the Python CLI, not this script)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VAULT_PASSWORD_FILE="$PROJECT_ROOT/.vault_password"
DOTENV_FILE="$PROJECT_ROOT/.env"

# 1. Check ANSIBLE_VAULT_PASSWORD environment variable
if [[ -n "${ANSIBLE_VAULT_PASSWORD:-}" ]]; then
    echo "$ANSIBLE_VAULT_PASSWORD"
    exit 0
fi

# 2. Check .vault_password file
if [[ -f "$VAULT_PASSWORD_FILE" ]]; then
    cat "$VAULT_PASSWORD_FILE"
    exit 0
fi

# 3. Load .env file if it exists (may set OP_SECRET)
if [[ -f "$DOTENV_FILE" ]]; then
    # shellcheck source=/dev/null
    set -a && source "$DOTENV_FILE" && set +a
fi

# 4. Check OP_SECRET environment variable (1Password secret reference)
if [[ -n "${OP_SECRET:-}" ]]; then
    op read -n "$OP_SECRET"
    exit $?
fi

# No password source found
echo "ERROR: No vault password source found." >&2
echo "" >&2
echo "Options:" >&2
echo "  1. Create password file: echo 'your-password' > $VAULT_PASSWORD_FILE && chmod 600 $VAULT_PASSWORD_FILE" >&2
echo "  2. Set environment variable: export ANSIBLE_VAULT_PASSWORD='your-password'" >&2
echo "  3. Use 1Password: Set OP_SECRET to a secret reference (e.g., op://vault/item/password)" >&2
echo "     You can copy this from 1Password with 'Copy Secret Reference'" >&2
echo "" >&2
echo "Environment variables can be set in: $DOTENV_FILE" >&2
exit 1

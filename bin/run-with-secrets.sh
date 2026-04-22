#!/usr/bin/env bash
# run-with-secrets.sh — resolve Ansible Vault secrets into env vars, then exec.
#
# Intended for wrapping MCP servers (and similar) so their configs never
# contain plaintext tokens. Secrets are fetched at spawn time via a single
# `dotfiles secret get -p <profile> -0 ...` call (one vault decrypt,
# null-separated output, byte-safe).
#
# Usage:
#   run-with-secrets.sh -p <profile> VAR=key.path [VAR=key.path ...] -- command [args...]
#
# Example:
#   run-with-secrets.sh -p private-adobe \
#     OUTLOOK_TENANT_ID=mcp_secrets.outlook.tenant_id \
#     OUTLOOK_CLIENT_ID=mcp_secrets.outlook.client_id \
#     -- outlook-mcp-auth --port 8080
#
# Exit codes:
#   0  — command executed (via exec; this script does not return)
#   2  — usage/parse error (missing --profile, missing --, malformed pair, unknown arg)
#   3  — secret resolution failed (CLI returned non-zero, or value count mismatch)
#   *  — any non-zero from the CLI is propagated

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES="${SCRIPT_DIR}/../dotfiles"

usage() {
    cat >&2 <<EOF
run-with-secrets.sh: resolve vault secrets into env, then exec a command.

Usage:
  run-with-secrets.sh -p <profile> VAR=key.path [VAR=key.path ...] -- command [args...]

  -p, --profile NAME   Vault profile to resolve from (required)
  VAR=key.path         Zero or more env-var / secret-path pairs
  --                   Separator between pairs and the real command
  command [args...]    The program to exec after secrets resolve
EOF
}

profile=""
vars=()
keys=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--profile)
            [[ $# -ge 2 ]] || { echo "run-with-secrets: --profile requires a value" >&2; exit 2; }
            profile="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        *=*)
            vars+=("${1%%=*}")
            keys+=("${1#*=}")
            shift
            ;;
        *)
            echo "run-with-secrets: unexpected argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$profile" ]]; then
    echo "run-with-secrets: --profile is required" >&2
    usage
    exit 2
fi

if [[ $# -eq 0 ]]; then
    echo "run-with-secrets: command required after --" >&2
    usage
    exit 2
fi

if [[ ${#keys[@]} -gt 0 ]]; then
    # One decrypt, N values, null-separated so any byte is safe.
    # `set -euo pipefail` + the explicit count check below guarantee we never
    # exec with a partially-populated env.
    i=0
    while IFS= read -r -d '' value; do
        if [[ $i -ge ${#vars[@]} ]]; then
            echo "run-with-secrets: CLI returned more values than requested" >&2
            exit 3
        fi
        export "${vars[i]}=$value"
        i=$((i + 1))
    done < <("$DOTFILES" secret get -p "$profile" -0 "${keys[@]}")

    if [[ $i -ne ${#keys[@]} ]]; then
        echo "run-with-secrets: expected ${#keys[@]} values, got $i" >&2
        exit 3
    fi
fi

exec "$@"

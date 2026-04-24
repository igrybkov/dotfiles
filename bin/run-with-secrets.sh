#!/usr/bin/env bash
# run-with-secrets.sh — resolve Ansible Vault secrets into env vars, then exec.
#
# Intended for wrapping MCP servers (and similar) so their configs never
# contain plaintext tokens. Secrets are fetched at spawn time via one
# `dotfiles secret get -p <profile> -0 ...` call per referenced profile
# (one vault decrypt per profile, null-separated output, byte-safe).
#
# Syntax for each pair:
#   VAR=key.path              — resolve from --profile's vault (default).
#   VAR=key.path@profile-name — resolve from `profile-name`'s vault instead.
#
# The `@profile-name` suffix routes that specific pair to a different profile's
# encrypted `secrets.yml`. Profile names may contain `/` (e.g. `@personal/productivity`).
# Splitting is on the LAST `@` so keys like `alpha.two@personal/adobe` parse
# deterministically. Callers that legitimately need `@` inside a key path and
# aren't using the override are out of scope — this syntax is reserved.
#
# Usage:
#   run-with-secrets.sh -p <profile> VAR=key.path[@profile] [VAR=...] -- command [args...]
#
# Examples:
#   run-with-secrets.sh -p private-personal-productivity \
#     OBSIDIAN_API_KEY_GARDEN=mcp_secrets.obsidian.digital_garden.api_key \
#     OBSIDIAN_API_KEY_ADOBE=mcp_secrets.obsidian_adobe.api_key@private-adobe \
#     -- obsidian-mcp-server
#
# Exit codes:
#   0  — command executed (via exec; this script does not return)
#   2  — usage/parse error (missing --profile, missing --, malformed pair,
#        empty @profile suffix, unknown arg)
#   3  — secret resolution failed (CLI returned non-zero, or value count mismatch)
#   *  — any non-zero from the CLI is propagated

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES="${SCRIPT_DIR}/../dotfiles"

usage() {
    cat >&2 <<EOF
run-with-secrets.sh: resolve vault secrets into env, then exec a command.

Usage:
  run-with-secrets.sh -p <profile> VAR=key.path[@profile] [VAR=...] -- command [args...]

  -p, --profile NAME       Default vault profile for pairs without @ suffix (required)
  VAR=key.path             Resolve from --profile's vault
  VAR=key.path@profile     Resolve from that profile's vault instead
  --                       Separator between pairs and the real command
  command [args...]        The program to exec after secrets resolve
EOF
}

profile=""
vars=()
keys=()
profiles_for_pair=()  # per-pair effective profile (filled after parse)

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
            var_name="${1%%=*}"
            raw="${1#*=}"
            # Split on LAST '@' for the optional profile override.
            if [[ "$raw" == *@* ]]; then
                keypart="${raw%@*}"
                profpart="${raw##*@}"
                if [[ -z "$profpart" ]]; then
                    echo "run-with-secrets: empty profile suffix in ${var_name}=${raw}" >&2
                    exit 2
                fi
                if [[ -z "$keypart" ]]; then
                    echo "run-with-secrets: empty key path in ${var_name}=${raw}" >&2
                    exit 2
                fi
                vars+=("$var_name")
                keys+=("$keypart")
                profiles_for_pair+=("$profpart")
            else
                vars+=("$var_name")
                keys+=("$raw")
                profiles_for_pair+=("")  # filled with $profile after parse
            fi
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

# Fill in default profile for pairs without explicit @override.
for i in "${!profiles_for_pair[@]}"; do
    if [[ -z "${profiles_for_pair[i]}" ]]; then
        profiles_for_pair[i]="$profile"
    fi
done

if [[ ${#keys[@]} -gt 0 ]]; then
    # Build the unique set of referenced profiles, preserving first-seen order.
    unique_profiles=()
    for p in "${profiles_for_pair[@]}"; do
        seen=0
        # bash 3.2: empty-array expansion is unsafe under `set -u`; ${arr[@]:-}
        # would inject an empty element, so guard the iteration explicitly.
        if [[ ${#unique_profiles[@]} -gt 0 ]]; then
            for u in "${unique_profiles[@]}"; do
                if [[ "$u" == "$p" ]]; then seen=1; break; fi
            done
        fi
        [[ $seen -eq 0 ]] && unique_profiles+=("$p")
    done

    # Resolve secrets one profile at a time, scattering values back by index.
    # Using an indexed array with explicit assignment so each pair's value
    # lands at its original index regardless of which profile-group resolves it.
    resolved=()
    for i in "${!vars[@]}"; do resolved[i]=""; done

    for up in "${unique_profiles[@]}"; do
        subkeys=()
        subidx=()
        for i in "${!profiles_for_pair[@]}"; do
            if [[ "${profiles_for_pair[i]}" == "$up" ]]; then
                subkeys+=("${keys[i]}")
                subidx+=("$i")
            fi
        done

        j=0
        while IFS= read -r -d '' value; do
            if [[ $j -ge ${#subidx[@]} ]]; then
                echo "run-with-secrets: CLI returned more values than requested for profile ${up}" >&2
                exit 3
            fi
            orig="${subidx[j]}"
            resolved[orig]="$value"
            j=$((j + 1))
        done < <("$DOTFILES" secret get -p "$up" -0 "${subkeys[@]}")

        if [[ $j -ne ${#subkeys[@]} ]]; then
            echo "run-with-secrets: expected ${#subkeys[@]} values for profile ${up}, got $j" >&2
            exit 3
        fi
    done

    for i in "${!vars[@]}"; do
        export "${vars[i]}=${resolved[$i]}"
    done
fi

exec "$@"

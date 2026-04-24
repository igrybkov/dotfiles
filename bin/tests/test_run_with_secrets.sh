#!/usr/bin/env bash
# Tests for bin/run-with-secrets.sh — runs the wrapper against a fake `dotfiles`
# CLI so the real vault isn't needed. Invoke directly; exits 0 iff all cases pass.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$(dirname "$SCRIPT_DIR")/run-with-secrets.sh"

[[ -x "$WRAPPER" ]] || { echo "FAIL: wrapper not executable at $WRAPPER" >&2; exit 1; }

# Fake `dotfiles` CLI that returns deterministic secrets for known keys and
# exits non-zero for anything else. Lookup tables are keyed by `<profile>:<key>`
# so multi-profile tests can assert correct routing. Lives in a tempdir placed
# alongside the wrapper via a shim so `../dotfiles` resolves to the fake.
TMPROOT="$(mktemp -d)"
trap 'rm -rf "$TMPROOT"' EXIT

# Mirror the layout run-with-secrets.sh expects: $SCRIPT_DIR/../dotfiles.
mkdir -p "$TMPROOT/bin"
cp "$WRAPPER" "$TMPROOT/bin/run-with-secrets.sh"
cat >"$TMPROOT/dotfiles" <<'EOF'
#!/usr/bin/env bash
# Fake dotfiles CLI. Accepts: secret get -p <profile> [-0] <key> [<key>...]
set -euo pipefail
[[ "$1" == "secret" && "$2" == "get" ]] || { echo "fake dotfiles: unexpected args: $*" >&2; exit 99; }
shift 2
profile=""
zero=0
keys=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--profile) profile="$2"; shift 2 ;;
        -0|--zero)    zero=1; shift ;;
        *)            keys+=("$1"); shift ;;
    esac
done
[[ -n "$profile" ]] || { echo "fake: missing profile" >&2; exit 2; }

# Per-profile secret table. bash 3.2 has no associative arrays, so use a
# case dispatch keyed by "profile:key".
lookup() {
    case "$1" in
        alpha:alpha.one)           printf '%s' "first" ;;
        alpha:alpha.two)           printf '%s' "second" ;;
        alpha:alpha.with_newlines) printf '%s' $'line1\nline2' ;;
        beta:beta.only)            printf '%s' "beta-value" ;;
        adobe/work:work.token)     printf '%s' "adobe-work-token" ;;
        *)                         return 1 ;;
    esac
}

for k in "${keys[@]}"; do
    if ! lookup "${profile}:${k}"; then
        echo "fake: missing key ${profile}:${k}" >&2
        exit 1
    fi
    if [[ $zero -eq 1 ]]; then
        printf '\0'
    else
        printf '\n'
    fi
done
EOF
chmod +x "$TMPROOT/dotfiles"

pass=0
fail=0

run() {
    local name="$1"; shift
    local expect_rc="$1"; shift
    local expect_stdout="$1"; shift
    local actual_stdout actual_rc
    set +e
    actual_stdout="$("$TMPROOT/bin/run-with-secrets.sh" "$@" 2>/dev/null)"
    actual_rc=$?
    set -e
    if [[ "$actual_rc" -eq "$expect_rc" && "$actual_stdout" == "$expect_stdout" ]]; then
        echo "PASS: $name"
        pass=$((pass + 1))
    else
        echo "FAIL: $name" >&2
        echo "  expected rc=$expect_rc stdout=$(printf %q "$expect_stdout")" >&2
        echo "  actual   rc=$actual_rc stdout=$(printf %q "$actual_stdout")" >&2
        fail=$((fail + 1))
    fi
}

# ---------- Single-profile (backward compat) ----------

# Happy path: two secrets resolved and exported.
# Single-quoting is intentional: ONE/TWO must expand inside the `sh -c` subshell,
# not here — the wrapper exports them before exec'ing sh.
# shellcheck disable=SC2016
run "happy path two secrets" 0 "first/second" \
    -p alpha ONE=alpha.one TWO=alpha.two -- sh -c 'printf "%s/%s" "$ONE" "$TWO"'

# Happy path with zero pairs: wrapper just execs.
run "no secrets requested" 0 "hi" \
    -p alpha -- sh -c 'printf hi'

# Secret with embedded newline survives -0 framing (safe byte-for-byte).
# shellcheck disable=SC2016  # BLK expands in the `sh -c` subshell.
run "secret with newlines preserved" 0 $'line1\nline2' \
    -p alpha BLK=alpha.with_newlines -- sh -c 'printf %s "$BLK"'

# Missing --profile.
run "missing profile arg" 2 "" \
    VAR=alpha.one -- true

# Missing -- separator (everything looks like a pair or unknown arg).
run "missing -- separator" 2 "" \
    -p alpha VAR=alpha.one true

# --profile with no value.
run "profile flag without value" 2 "" \
    -p

# Unresolvable key → CLI exits 1 → wrapper aborts before exec.
run "unresolvable key aborts before exec" 3 "" \
    -p alpha GONE=alpha.missing -- sh -c 'echo SHOULD_NOT_RUN'

# ---------- Multi-profile @override ----------

# Default profile resolves bare key; @profile routes one pair to a different vault.
# shellcheck disable=SC2016  # $A $B expand in sh -c, not here.
run "mixed default and @override" 0 "first|beta-value" \
    -p alpha \
    A=alpha.one \
    B=beta.only@beta \
    -- sh -c 'printf "%s|%s" "$A" "$B"'

# All pairs use @override — each routes to its own profile, ordering preserved.
# shellcheck disable=SC2016
run "all pairs @override, ordering preserved" 0 "first|beta-value|second" \
    -p alpha \
    X=alpha.one@alpha \
    Y=beta.only@beta \
    Z=alpha.two@alpha \
    -- sh -c 'printf "%s|%s|%s" "$X" "$Y" "$Z"'

# Profile name containing slash (nested profile name).
# shellcheck disable=SC2016
run "@profile with slash in name" 0 "adobe-work-token" \
    -p alpha \
    TOK=work.token@adobe/work \
    -- sh -c 'printf %s "$TOK"'

# Empty @profile suffix is a parse error.
run "empty @profile suffix rejected" 2 "" \
    -p alpha VAR=alpha.one@ -- true

# Empty key path with @profile is a parse error.
run "empty key with @profile rejected" 2 "" \
    -p alpha VAR=@beta -- true

# Unresolvable key in an @override profile aborts before exec.
run "@override unresolvable key aborts" 3 "" \
    -p alpha \
    OK=alpha.one \
    BAD=missing.key@beta \
    -- sh -c 'echo SHOULD_NOT_RUN'

# @override to a profile the fake CLI rejects (no profile called "ghost").
# The fake CLI returns empty output for unknown profiles/keys; the wrapper
# catches the value-count mismatch.
run "@override to unknown profile aborts" 3 "" \
    -p alpha \
    G=alpha.one@ghost \
    -- sh -c 'echo SHOULD_NOT_RUN'

# ---------- Help / usage ----------

# -h prints usage and exits 0.
set +e
"$TMPROOT/bin/run-with-secrets.sh" -h >/dev/null 2>&1
rc=$?
set -e
if [[ $rc -eq 0 ]]; then
    echo "PASS: -h exits 0"
    pass=$((pass + 1))
else
    echo "FAIL: -h returned $rc" >&2
    fail=$((fail + 1))
fi

echo
echo "Summary: $pass passed, $fail failed"
[[ $fail -eq 0 ]]

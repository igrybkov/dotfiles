#!/usr/bin/env bash
# Tests for bin/run-with-secrets.sh — runs the wrapper against a fake `dotfiles`
# CLI so the real vault isn't needed. Invoke directly; exits 0 iff all cases pass.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$(dirname "$SCRIPT_DIR")/run-with-secrets.sh"

[[ -x "$WRAPPER" ]] || { echo "FAIL: wrapper not executable at $WRAPPER" >&2; exit 1; }

# Fake `dotfiles` CLI that returns deterministic secrets for known keys and
# exits non-zero for anything else. Lives in a tempdir placed alongside the
# wrapper via a shim directory so the wrapper's `../dotfiles` lookup finds it.
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

# Use a function-based lookup — bash 3.2 (macOS default) doesn't support
# associative arrays, and `env bash` resolves to /bin/bash on macOS.
lookup() {
    case "$1" in
        alpha.one)           printf '%s' "first" ;;
        alpha.two)           printf '%s' "second" ;;
        alpha.with_newlines) printf '%s' $'line1\nline2' ;;
        *)                   return 1 ;;
    esac
}

for k in "${keys[@]}"; do
    if ! lookup "$k"; then
        echo "fake: missing key $k" >&2
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

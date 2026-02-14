#shellcheck disable=SC1107,SC1091,SC2148
# Homebrew shell setup
if command -v brew &>/dev/null; then
  _evalcache brew shellenv
fi

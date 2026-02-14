#shellcheck disable=SC1107,SC1091,SC2148
# Homebrew shell setup
if command -v docker &>/dev/null; then
  _evalcache docker completion zsh
fi

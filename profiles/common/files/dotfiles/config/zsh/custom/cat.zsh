#shellcheck disable=SC1107,SC1091,SC2148
# Replace cat with bat
if command -v bat &>/dev/null; then
  alias cat="bat --paging=never --style=plain"
fi

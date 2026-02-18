#shellcheck disable=SC1107,SC1091,SC2148
# Use nvim instead of vim/vi when available
if command -v nvim &>/dev/null; then
  alias vim="nvim"
  alias vi="nvim"
elif command -v vim &>/dev/null; then
  alias vi="vim"
fi

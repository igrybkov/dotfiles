#shellcheck disable=SC1107,SC1091,SC2148
if [ -f "${HOME}/.config/op/plugins.sh" ]; then
  source "${HOME}/.config/op/plugins.sh"
fi

if command -v op &>/dev/null; then
  # if [ -z "$_comps[op]" ]; then
  _evalcache_autocomplete op completion zsh
  # fi
  compdef _op op
fi

#shellcheck disable=SC1107,SC1091,SC2148
if command -v faas-cli &>/dev/null; then
  if [ -z "${_comps[faas - cli]}" ]; then
    _evalcache faas-cli completion --shell zsh
  fi

  faas-cli() {
    local FAAS_CLI_BIN
    FAAS_CLI_BIN="$(/usr/bin/which faas-cli)"
    $FAAS_CLI_BIN "$@"
  }
fi

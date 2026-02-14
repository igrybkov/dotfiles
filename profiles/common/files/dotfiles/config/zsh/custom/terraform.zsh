#shellcheck disable=SC1107,SC1091,SC2148
alias tf="terraform"
alias tg="terragrunt"

if command -v tfenv &>/dev/null; then
  alias tfv="tfenv"
fi

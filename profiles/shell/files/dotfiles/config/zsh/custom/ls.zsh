#shellcheck disable=SC1107,SC1091,SC2148
# Replace ls with eza
if command -v eza &>/dev/null; then
  alias ls="eza -gh -s=type --git"
fi

alias l=ls
alias sl="ls"

# Colors for ls
alias ll="ls -l"
alias lla="ls -la"

# List only directories
alias lsd="ls -D"

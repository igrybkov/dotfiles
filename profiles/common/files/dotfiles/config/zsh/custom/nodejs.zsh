#shellcheck disable=SC1107,SC1091,SC2148
# Remove NVM related lines from ${ZDOTDIR:-$HOME}rc since we use custom plugin for that
sed -i '' -e '/NVM_DIR/d' "$(realpath "${ZDOTDIR:-$HOME}"/.zshrc)"
sed -i '' -e '/^$/N;/^\n$/D' "$(realpath "${ZDOTDIR:-$HOME}"/.zshrc)"

# Shortcuts
alias y="yarn"

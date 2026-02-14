#shellcheck disable=SC1107,SC1091,SC2148
alias zsh-cache-reload='rm -rf ~/.zcompdump ~/.antidote ${ZDOTDIR:-$HOME}-evalcache ${ZDOTDIR:-$HOME}/plugins.zsh'
alias zsh-antidote-reload='rm -rf ~/Library/Caches/antidote/ ${ZDOTDIR:-$HOME}/plugins.zsh ~/.antidote/'

# Enable bash-style comments in zsh allowing for comments to be written with a `#` at the beginning of a line.
setopt interactivecomments

# Enable the `HIST_IGNORE_SPACE` option to prevent commands starting with a space from being saved to the history.
setopt HIST_IGNORE_SPACE

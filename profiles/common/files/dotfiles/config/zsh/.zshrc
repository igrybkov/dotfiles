# This file is sourced in interactive shells only.

# Uncomment this if you want to profile shell start time as well as the last line
# Helpful article: https://htr3n.github.io/2018/07/faster-zsh/
#zmodload zsh/zprof

#shellcheck disable=SC1107,SC1091,SC2148,SC1090

if [ ! -f ~/.local/bin/starship ]; then
  mkdir -p ~/.local/bin/
  curl -sS https://starship.rs/install.sh | sh -s -- --bin-dir ~/.local/bin --yes
fi
eval "$(~/.local/bin/starship init zsh)"

autoload -Uz compinit
if [ ! -f "${ZDOTDIR:-$HOME}/.zcompdump" ] || [ "$(date +'%j')" != "$(/usr/bin/stat -f '%Sm' -t '%j' "${ZDOTDIR:-$HOME}/.zcompdump")" ]; then
  compinit
else
  compinit -C
fi

# shellcheck disable=SC2034
KEYTIMEOUT=1
# shellcheck disable=SC2034
VIM_MODE_ESC_PREFIXED_WANTED='bdfhul.g' # Default is 'bdf.g'

zsh_plugins=${ZDOTDIR:-$HOME}/plugins
if [[ ! -f ${zsh_plugins}.zsh || ! ${zsh_plugins}.zsh -nt ${zsh_plugins}.txt ]]; then
  (
    if [ ! -d "$HOME/.antidote" ]; then
      git clone -q --depth=1 https://github.com/mattmc3/antidote.git "${ZDOTDIR:-${ZDOTDIR:-$HOME}}/.antidote"
    fi

    # there's some cache related bug when this function cached incorrectly, so I just unfunction it
    builtin unfunction __antidote_core &>/dev/null
    source ~/.antidote/antidote.zsh

    echo "#shellcheck disable=all" >"${zsh_plugins}.zsh"
    antidote bundle <"${zsh_plugins}.txt" >>"${zsh_plugins}.zsh"
  )
fi

# Suppress the warning for VSCode. It appears because zsh-notify doesn't support vscode,
# but I can't suppress zsh-notify's warning specifically, so this is the easiest way right now.
if [[ "$TERM_PROGRAM" == "vscode" || "$TERM_PROGRAM" == "tmux" || "$TERM_PROGRAM" == "WezTerm" ]]; then
  source "${zsh_plugins}.zsh" &>/dev/null
else
  source "${zsh_plugins}.zsh" &>/dev/null
fi

source "${ZDOTDIR:-$HOME}/evalcache.zsh"

for file in "${ZDOTDIR:-$HOME}"/functions/*; do
  autoload -Uz "$(basename "${file}")"
done

for file in "${ZDOTDIR:-$HOME}"/custom/*.zsh; do
  source "$file"
done

# Include environment-specific configuration
test -e "${HOME}/.zenv" && source "${HOME}/.zenv"

# tabtab source for packages
# uninstall by removing these lines
if [[ -f ~/.config/tabtab/__tabtab.zsh ]]; then
  source ~/.config/tabtab/__tabtab.zsh
fi

precmd() {
  # sets the tab title to current dir
  echo -ne "\e]1;${PWD##*/}\a"
}

# Uncomment this if you want to profile shell start time as well as the 1st line
#zprof | head -n 20

autoload -U +X bashcompinit && bashcompinit
complete -o nospace -C /opt/homebrew/bin/terraform terraform

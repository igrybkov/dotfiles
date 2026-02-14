#shellcheck disable=SC1107,SC1091,SC2148,SC2034

##############################################################################
# History Configuration
##############################################################################
HISTSIZE=5000                      #How many lines of history to keep in memory
HISTFILE=${ZDOTDIR:-$HOME}_history #Where to save history to disk
SAVEHIST=15000                     #Number of history entries to save to disk
HISTDUP=erase                      #Erase duplicates in the history file
setopt appendhistory               #Append history to the history file (no overwriting)
setopt sharehistory                #Share history across terminals
setopt incappendhistory            #Immediately append to the history file, not just when a term is killed

if ! [ -x "$(command -v fzf)" ]; then
  echo "WARNING: fzf missing - history search will not work"
fi

ZSH_FZF_HISTORY_SEARCH_EVENT_NUMBERS=0
ZSH_FZF_HISTORY_SEARCH_DATES_IN_SEARCH=0
ZSH_FZF_HISTORY_SEARCH_REMOVE_DUPLICATES=1
ZSH_FZF_HISTORY_SEARCH_END_OF_LINE=1
ZSH_FZF_HISTORY_SEARCH_FZF_EXTRA_ARGS="--layout=reverse"

# Always return full history
alias history="history 1"

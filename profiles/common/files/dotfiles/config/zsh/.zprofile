# This file is loaded by all Zsh instances thanks to customization in .zshenv.
# It is the perfect place to initialize environment variables

if [ -z "$ZSH_CACHE_DIR" ]; then
  ZSH_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/zsh"
fi

#
# Browser
#
if [[ "$OSTYPE" == darwin* ]]; then
  export BROWSER='open'
fi

#
# Editors
#

export EDITOR='vim'
export VISUAL='vim'
export PAGER='less'

#
# Language
#

if [[ -z "$LANG" ]]; then
  export LC_ALL='en_US.UTF-8'
  export LANG='en_US.UTF-8'
fi

#
# Paths
#

# Ensure path arrays do not contain duplicates.
typeset -gU cdpath fpath mailpath path

# Set directories used by pj plugin
PROJECT_PATHS=(
  ~/Projects
  #~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/
  ~/Obsidian
  $PROJECT_PATHS
)

# Set the list of directories that Zsh searches for programs.
path=(
  ~/bin
  ~/.bin
  ~/.local/bin
  ~/.composer/vendor/bin
  /usr/local/opt/mysql-client/bin
  /usr/local/{bin,sbin}
  /opt/homebrew/anaconda3/bin
  $path
)

fpath=(
  ${ZDOTDIR:-$HOME}/functions
  ${ZDOTDIR:-$HOME}/completion
  ${ZDOTDIR:-$HOME}-evalcache/completion
  /opt/homebrew/share/zsh/{functions,completions,site-functions}
  $fpath
)

#
# Less
#

# Set the default Less options.
# Mouse-wheel scrolling has been disabled by -X (disable screen clearing).
# Remove -X and -F (exit if the content fits on one screen) to enable it.
export LESS='-F -g -i -M -R -S -w -X -z-4'

# Set the Less input preprocessor.
# Try both `lesspipe` and `lesspipe.sh` as either might exist on a system.
# shellcheck disable=SC1009,SC1073,SC1072
if (( $#commands[(i)lesspipe(|.sh)] )); then
  export LESSOPEN="| /usr/bin/env $commands[(i)lesspipe(|.sh)] %s 2>&-"
fi

export CLICOLOR=1;
export LSCOLORS=exfxcxdxbxegedabagacad; # It is the default value on OSX, so this line can be omitted

ENHANCD_DOT_SHOW_FULLPATH=1
ENHANCD_DISABLE_HOME=1
ENHANCD_DISABLE_DOT=1

PURE_GIT_UNTRACKED=' %B%F{green}...%f%b'
PURE_GIT_DIRTY=' %B%F{yellow}✚%f%b'
PURE_GIT_STAGED=' %F{yellow}●%f'
PURE_GIT_UNMERGED=' %B%F{red}✖%f%b'

# Enable autocorrection
setopt correct

# NVM directory
if [ -d "$HOME/.nvm" ]; then
  export NVM_DIR="$HOME/.nvm"
fi

# Include environment-specific configuration
test -e "${HOME}/.zprofile.env" && source "${HOME}/.zprofile.env"

# Fixing segfault bug in ansible
export no_proxy="*"

# Allow python to load modules from src/lib directories
# export PYTHONPATH="./src:./lib:.:$PYTHONPATH"

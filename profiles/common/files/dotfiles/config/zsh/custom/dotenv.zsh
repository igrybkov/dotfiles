#shellcheck disable=SC1107,SC1091,SC2148
# Source: https://github.com/ohmyzsh/ohmyzsh/blob/master/plugins/dotenv/dotenv.plugin.zsh
# Modified to shut it down on the first run to avoid conflicts with the instant prompt.

## Settings

# Filename of the dotenv file to look for
#shellcheck disable=SC2223
: ${ZSH_DOTENV_FILE:=.env}

# Path to the file containing allowed paths
#shellcheck disable=SC2223
: ${ZSH_DOTENV_ALLOWED_LIST:="${ZSH_CACHE_DIR:-$ZSH/cache}/dotenv-allowed.list"}
#shellcheck disable=SC2223
: ${ZSH_DOTENV_DISALLOWED_LIST:="${ZSH_CACHE_DIR:-$ZSH/cache}/dotenv-disallowed.list"}

## Functions

source_env() {
  if [[ ! -f "$ZSH_DOTENV_FILE" ]]; then
    return
  fi

  if [[ "$ZSH_DOTENV_PROMPT" != false ]]; then
    local confirmation dirpath="${PWD:A}"

    # make sure there is an (dis-)allowed file
    touch "$ZSH_DOTENV_ALLOWED_LIST"
    touch "$ZSH_DOTENV_DISALLOWED_LIST"

    # early return if disallowed
    if command grep -Fx -q "$dirpath" "$ZSH_DOTENV_DISALLOWED_LIST" &>/dev/null; then
      return
    fi

    # check if current directory's .env file is allowed or ask for confirmation
    if ! command grep -Fx -q "$dirpath" "$ZSH_DOTENV_ALLOWED_LIST" &>/dev/null; then
      if [[ "$ZSH_DOTENV_LEAVE_IF_NOT_ALLOWED" == true ]]; then
        return
      fi
      # get cursor column and print new line before prompt if not at line beginning
      local column
      echo -ne "\e[6n" >/dev/tty
      # shellcheck disable=SC2034
      read -t 1 -r -s -d R column </dev/tty
      column="${column##*\[*;}"
      [[ $column -eq 1 ]] || echo

      # print same-line prompt and output newline character if necessary
      echo -n "dotenv: found '$ZSH_DOTENV_FILE' file. Source it? ([Y]es/[n]o/[a]lways/n[e]ver) "
      read -r -k 1 confirmation
      [[ "$confirmation" = $'\n' ]] || echo

      # check input
      case "$confirmation" in
      [nN]) return ;;
      [aA]) echo "$dirpath" >>"$ZSH_DOTENV_ALLOWED_LIST" ;;
      [eE])
        echo "$dirpath" >>"$ZSH_DOTENV_DISALLOWED_LIST"
        return
        ;;
      *) ;; # interpret anything else as a yes
      esac
    fi
  fi

  # test .env syntax
  zsh -fn "$ZSH_DOTENV_FILE" || {
    echo "dotenv: error when sourcing '$ZSH_DOTENV_FILE' file" >&2
    return 1
  }

  setopt localoptions allexport
  # shellcheck disable=SC1090
  source "$ZSH_DOTENV_FILE"
}

autoload -U add-zsh-hook
add-zsh-hook chpwd source_env

ZSH_DOTENV_LEAVE_IF_NOT_ALLOWED=true source_env

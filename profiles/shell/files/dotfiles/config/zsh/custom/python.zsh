#shellcheck disable=SC1107,SC1091,SC2148
#shellcheck disable=SC1090,SC1091,SC2148
# alias pip="pip3 "
# alias python="python3 "

if [[ -z "$ZSH_PYTHON_VENV_DIR" ]]; then
  ZSH_PYTHON_VENV_DIR="./.venv"
fi

if command -v uv &>/dev/null; then
  _evalcache_autocomplete uv generate-shell-completion zsh
  compdef _uv uv
fi

if command -v ruff &>/dev/null; then
  _evalcache_autocomplete ruff generate-shell-completion zsh
fi
compdef _ruff ruff

alias pyvenv="uv venv"

python_venv() {
  if [[ -d "$ZSH_PYTHON_VENV_DIR" ]]; then
    source "$ZSH_PYTHON_VENV_DIR/bin/activate" >/dev/null
    PYVENV_PATH="$PWD"
  elif [[ -z "$PYVENV_PATH" ]]; then
    if git rev-parse --show-toplevel >/dev/null 2>&1; then
      GIT_TOPLEVEL=$(git rev-parse --show-toplevel)
      if [[ -d "$GIT_TOPLEVEL/$ZSH_PYTHON_VENV_DIR" ]]; then
        source "$GIT_TOPLEVEL/$ZSH_PYTHON_VENV_DIR/bin/activate" >/dev/null
        PYVENV_PATH="$GIT_TOPLEVEL"
      elif [[ -d "$GIT_TOPLEVEL/$ZSH_PYTHON_VENV_DIR" ]]; then
        source "$ZSH_PYTHON_VENV_DIR/bin/activate" >/dev/null
        PYVENV_PATH="$GIT_TOPLEVEL"
      fi
    fi
    # if PYVENV_PATH is empty, we're not in a venv
    return
  elif echo "$PWD" | grep -q "$PYVENV_PATH"; then
    return
  elif command -v deactivate >/dev/null; then
    deactivate
    unset PYVENV_PATH
  elif command -v conda >/dev/null; then
    conda deactivate
    unset PYVENV_PATH
  fi
  # when you cd into a folder that contains $ZSH_PYTHON_VENV_DIR
  # when you cd into a folder that doesn't
  #  >/dev/null 2>&1
}
autoload -U add-zsh-hook
add-zsh-hook chpwd python_venv

# Activate virtual environment on startup
python_venv >/dev/null

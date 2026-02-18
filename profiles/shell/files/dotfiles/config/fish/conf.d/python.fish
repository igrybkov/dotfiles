if status is-interactive
    # Add UV completions
    if type -q uv
        _evalcache uv generate-shell-completion fish
    end
    # Add Ruff completions
    if type -q ruff
        _evalcache ruff generate-shell-completion fish
    end
    # Add uvx completions
    if type -q uvx
        _evalcache uvx --generate-shell-completion fish
    end
end

function __activate_python_venv --on-event fish_prompt
    set -l VENV_FILE_PATH ".venv/bin/activate.fish"
    # Activate virtual environment from the current directory
    if test -f "$VENV_FILE_PATH"
        # Only activate the virtual environment if it doesn't match the current one
        if test -z "$VIRTUAL_ENV" -o "$VIRTUAL_ENV" != "$PWD"
            source "$VENV_FILE_PATH" >/dev/null
        end
        return
    end
    # Check if the current directory is a git repository and activate the virtual environment from the git root
    if git rev-parse --show-toplevel >/dev/null 2>&1
        set -l GIT_TOPLEVEL (git rev-parse --show-toplevel)
        set -l VENV_FILE_PATH "$GIT_TOPLEVEL/.venv/bin/activate.fish"
        if test -f "$VENV_FILE_PATH"
            # Only activate the virtual environment if it doesn't match the current one
            if test -z "$VIRTUAL_ENV" -o "$VIRTUAL_ENV" != "$PWD"
                source "$VENV_FILE_PATH" >/dev/null
            end
            source "$VENV_FILE_PATH" >/dev/null
            return
        end
    end
    # Deactivate the virtual environment if it doesn't match the current directory
    if test -n "$VIRTUAL_ENV"; and functions -q deactivate
        deactivate
    end
end

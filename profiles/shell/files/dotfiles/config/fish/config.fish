set -gx XDG_CONFIG_HOME $HOME/.config
set -gx XDG_CACHE_HOME $HOME/.cache
set -gx XDG_DATA_HOME $HOME/.local/share

if type -q nvim
    set -gx EDITOR nvim
else
    set -gx EDITOR vim
end
set -gx GIT_EDITOR $EDITOR
if type -q code
    set -gx VISUAL code
else
    set -gx VISUAL $EDITOR
end
set -gx PAGER bat

# Modify PATH
fish_add_path --global --move "$HOME/.node_modules/bin"
fish_add_path --global --move "$HOME/.local/bin"

# Commands to run in interactive sessions can go here
if status is-interactive
    if type -q starship
        _evalcache starship init fish
    end
    # Regenerate completions when they're missing or older than 3 days
    # The delay is set because the process, while being completely asynchronous,
    # still takes about five seconds, and triggering it every time I open a new terminal
    # is a waste of resources.
    if not test -d "$XDG_CACHE_HOME/fish/generated_completions" \
        || test $(path mtime -R $XDG_CACHE_HOME/fish/generated_completions) -gt $(math '60*60*24*3')
        fish_update_completions_detach=true fish_update_completions
    end
    # Set `pj` plugin
    set -gx PROJECT_PATHS ~/Projects ~/Obsidian
    # Set color for autosuggestions
    set fish_color_autosuggestion gray
end

# Disable the fish greeting message
set fish_greeting ""

if [ -d $XDG_CONFIG_HOME/fish/local ]
    for file in $XDG_CONFIG_HOME/fish/local/*.fish
        source $file
    end
end

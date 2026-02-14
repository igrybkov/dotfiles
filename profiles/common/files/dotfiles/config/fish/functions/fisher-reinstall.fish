# Reinstall all Fisher plugins from managed_fish_plugins file.
#
# This function performs a clean reinstall of all Fisher plugins:
# 1. Creates a lock file to prevent recursive sync attempts
# 2. Optionally recreates the fisher_path directory (if using custom path)
# 3. Bootstraps Fisher itself if not available
# 4. Installs all plugins listed in managed_fish_plugins
#
# The lock file mechanism is necessary because fisher install spawns child
# fish processes that would otherwise trigger 00_fisher.fish's sync check.
#
# Options:
#   --quiet, -q  Suppress output on success (errors still shown)
#
# Exit codes:
#   0 - Success
#   1 - managed_fish_plugins file not found
#   2 - Fisher bootstrap failed
#   Other - Exit code from fisher install

function fisher-reinstall --description "Reinstall all Fisher plugins"
    argparse q/quiet -- $argv
    or return 1

    set -l lock_file /tmp/.fisher_sync_in_progress
    set -l managed_plugins_file ~/.config/fish/managed_fish_plugins

    # Validate managed_fish_plugins exists before doing anything
    if not test -f $managed_plugins_file
        echo "fisher-reinstall: managed_fish_plugins file not found: $managed_plugins_file" >&2
        return 1
    end

    # Set lock to prevent repeated sync attempts from child fish processes
    touch $lock_file

    # Helper to clean up lock file on any exit
    function __fisher_reinstall_cleanup --on-event fish_exit
        rm -f /tmp/.fisher_sync_in_progress
        functions -e __fisher_reinstall_cleanup
    end

    # Recreate fisher_path directory if using a custom (non-default) path
    # This ensures a clean slate for plugin installation
    if test -n "$fisher_path" \
            -a "$fisher_path" != "$__fish_config_dir" \
            -a "$fisher_path" != "$__fish_user_data_dir" \
            -a -d "$fisher_path"
        test -z "$_flag_quiet"; and echo "Recreating fisher_path directory: $fisher_path"
        rm -rf "$fisher_path"
        mkdir -p "$fisher_path/functions" "$fisher_path/completions" "$fisher_path/conf.d"
    end

    # Bootstrap Fisher if not available
    if not functions -q fisher
        test -z "$_flag_quiet"; and echo "Fisher not found, bootstrapping..."
        if not curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
            echo "fisher-reinstall: failed to download Fisher" >&2
            rm -f $lock_file
            functions -e __fisher_reinstall_cleanup
            return 2
        end
        if set -q _flag_quiet
            fisher install jorgebucaran/fisher >/dev/null 2>&1
        else
            fisher install jorgebucaran/fisher
        end
        if test $status -ne 0
            echo "fisher-reinstall: failed to install Fisher" >&2
            rm -f $lock_file
            functions -e __fisher_reinstall_cleanup
            return 2
        end
    end

    # Install plugins from managed_fish_plugins (skip comments and empty lines)
    set -l plugins (grep -vE '^\s*(#|$)' $managed_plugins_file)
    if test (count $plugins) -eq 0
        test -z "$_flag_quiet"; and echo "fisher-reinstall: no plugins found in $managed_plugins_file"
        rm -f $lock_file
        functions -e __fisher_reinstall_cleanup
        return 0
    end

    if set -q _flag_quiet
        printf '%s\n' $plugins | fisher install >/dev/null 2>&1
    else
        printf '%s\n' $plugins | fisher install
    end
    set -l result $status

    # Clean up
    rm -f $lock_file
    functions -e __fisher_reinstall_cleanup

    if test $result -eq 0
        test -z "$_flag_quiet"; and echo "Fisher: Successfully installed "(count $plugins)" plugin(s)"
    end

    return $result
end

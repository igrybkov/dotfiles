# Fisher Plugin Manager - Custom Path Configuration
#
# This file configures Fisher to install plugins to a separate directory
# (~/.config/fish/fisher) instead of polluting the main config directory.
# It also handles automatic plugin synchronization on shell startup.
#
# Files involved:
#   - managed_fish_plugins: Source of truth for desired plugins (version controlled)
#   - fish_plugins: Fisher's record of installed plugins (auto-generated)
#   - fisher/: Directory containing installed plugin files
#
# Sync triggers (any of these cause reinstall):
#   - fisher/ directory missing
#   - fish_plugins file missing
#   - managed_fish_plugins newer than fish_plugins
#
# The lock file (/tmp/.fisher_sync_in_progress) prevents infinite loops when
# fisher install spawns child fish processes.

set -g fisher_path $__fish_config_dir/fisher

# Add Fisher paths to fish's search paths (prepend for priority)
set -p fish_function_path $fisher_path/functions
set -p fish_complete_path $fisher_path/completions

# Automatic plugin synchronization
set -l managed_plugins_file $__fish_config_dir/managed_fish_plugins
set -l installed_plugins_file $__fish_config_dir/fish_plugins
set -l lock_file /tmp/.fisher_sync_in_progress

if test -e $lock_file
    # Sync already in progress (we're a child process), skip check
else if test -e $managed_plugins_file -a -s $managed_plugins_file
    # Determine if sync is needed
    set -l needs_sync false

    if not test -d $fisher_path
        set needs_sync true
    else if not test -e $installed_plugins_file
        set needs_sync true
    else if test $managed_plugins_file -nt $installed_plugins_file
        set needs_sync true
    end

    if test $needs_sync = true
        # Source fisher-reinstall function if not already loaded
        # (functions -q doesn't trigger autoloading during early boot)
        set -l reinstall_func $__fish_config_dir/functions/fisher-reinstall.fish
        if not functions -q fisher-reinstall; and test -f $reinstall_func
            source $reinstall_func
        end

        if functions -q fisher-reinstall
            fisher-reinstall --quiet
            if test $status -ne 0
                echo "Fisher: Reinstall failed. Run 'fisher-reinstall' for details." >&2
            end
        else
            echo "Fisher: Sync needed but fisher-reinstall function not found." >&2
        end
    end
end

# Source Fisher plugin conf.d files
for file in $fisher_path/conf.d/*.fish
    if test -r $file
        source $file
    end
end

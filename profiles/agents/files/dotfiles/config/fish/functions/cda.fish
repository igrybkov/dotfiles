# cda - Quick jump to worktree
# Thin wrapper over the cda script that handles cd
#
# Usage:
#   cda              - Fuzzy search all worktrees
#   cda main         - Go to main repo
#   cda feature-auth - Go to feature-auth worktree

function cda --description 'Quick jump to worktree'
    # cda script outputs the path, we just cd to it
    set -l target_path (command cda $argv)
    set -l exit_code $status

    if test $exit_code -ne 0
        return $exit_code
    end

    if test -n "$target_path" -a -d "$target_path"
        cd "$target_path"
    else
        return 1
    end
end

# Completions - suggest available worktrees
complete -c cda -f -a "(hive wt list 2>/dev/null | string split ':' -f 1)" -d "Worktree"

# cdwt - Navigate to git worktrees
# Usage:
#   cdwt              - List worktrees and select with fzf
#   cdwt feature-auth - Go to feature-auth worktree
#   cdwt main         - Go to main repo

function cdwt --description 'Navigate to a git worktree'
    set -l target $argv[1]

    # No argument - list worktrees (use fzf if available)
    if test -z "$target"
        # Get all worktrees via git worktree list (native git command)
        set -l worktrees (git worktree list --porcelain | string match -r '^worktree .*' | string replace 'worktree ' '')

        if test (count $worktrees) -eq 0
            echo "No worktrees found"
            return 1
        end

        # If only main repo, nothing to navigate to
        if test (count $worktrees) -eq 1
            echo "Only main repo exists, no other worktrees"
            return 1
        end

        # Use fzf if available
        if type -q fzf
            set -l selected (git worktree list | fzf --prompt="Select worktree: " --height=40% --reverse | awk '{print $1}')
            if test -n "$selected"
                cd "$selected"
                return 0
            end
            return 1
        else
            # No fzf - just list them
            echo "Available worktrees:"
            git worktree list
            echo ""
            echo "Usage: cdwt <name>"
            return 1
        end
    end

    # Special case: "main" or "1" goes to main repo
    if test "$target" = "main" -o "$target" = "1"
        if command -q git-worktree-path
            set -l main_path (git-worktree-path main 2>/dev/null)
            if test -d "$main_path"
                cd "$main_path"
                return 0
            end
        end
        # Fallback
        set -l git_root (git rev-parse --show-toplevel 2>/dev/null)
        if test -n "$git_root"
            cd "$git_root"
            return 0
        end
        echo "Could not find main repo"
        return 1
    end

    # Try git-worktree-path first
    if command -q git-worktree-path
        set -l worktree_path (git-worktree-path "$target" 2>/dev/null)
        if test -d "$worktree_path"
            cd "$worktree_path"
            return 0
        end

        # Legacy support: try agent-N format for numeric input
        if string match -qr '^[0-9]+$' "$target"
            set -l agent_path (git-worktree-path "agent-$target" 2>/dev/null)
            if test -d "$agent_path"
                cd "$agent_path"
                return 0
            end
        end
    end

    # Fallback: try as full path
    if test -d "$target"
        if git -C "$target" rev-parse --git-dir >/dev/null 2>&1
            cd "$target"
            return 0
        end
    end

    echo "Worktree not found: $target"
    echo ""
    echo "Available worktrees:"
    git worktree list
    return 1
end

# Completions - suggest available worktrees
complete -c cdwt -f -a "(git-worktree-path --list 2>/dev/null | string split ':' -f 1)" -d "Worktree"

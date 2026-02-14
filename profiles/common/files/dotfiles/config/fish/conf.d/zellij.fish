if not type -q zellij
    return
end

# Get the main repository path (not worktree)
# Returns the main repo even when called from a worktree
function __zellij_get_main_repo
    set -l git_common_dir (git rev-parse --git-common-dir 2>/dev/null)
    if test -z "$git_common_dir"
        pwd
        return
    end
    # Resolve to absolute path and get parent (main repo is parent of .git)
    dirname (realpath "$git_common_dir")
end

function __zellij_get_session_name
    echo (basename (__zellij_get_main_repo) | string lower | string replace ' ' '-')
end

function zz --wraps='zellij' --description 'Attach or create a zellij session named after the current directory'
    if test (count $argv) -eq 0
        set -l git_root (git rev-parse --show-toplevel 2>/dev/null)
        if test -n "$git_root"
            cd $git_root
        end
        zellij attach --create (__zellij_get_session_name)
        return
    end

    zellij $argv
end

# Claude Code layout
function zcc --description 'Open zellij with claude agent'
    HIVE_AGENT=claude zc $argv
end

# Cursor layout
function zcu --description 'Open zellij with cursor agent'
    HIVE_AGENT=agent zc $argv
end

# Copilot CLI layout
function zcp --description 'Open zellij with copilot agent'
    HIVE_AGENT=copilot zc $argv
end

# Codex layout
function zco --description 'Open zellij with codex agent'
    HIVE_AGENT=codex zc $argv
end

# Gemini layout
function zcg --description 'Open zellij with gemini agent'
    HIVE_AGENT=gemini zc $argv
end

# Auto-detect and open appropriate AI coding tool layout
# Delegates all agent detection and configuration to hive zellij
# If a project name is passed as $1, jumps to that project first (like `pj <project> && zc`)
function zc --description 'Open zellij profile for available AI coding tool'
    # If a project name is provided, jump to it first using pj
    if test (count $argv) -gt 0
        if not type -q pj
            echo "Error: pj command not found. Install the pj plugin or remove the project argument."
            return 1
        end
        pj $argv[1]
        or return $status
    end

    # Delegate to hive zellij for agent detection and session management
    hive zellij
end

# Completions for zc - suggest projects from pj (only if pj plugin is available)
if type -q pj
    complete -c zc -f -a '(__project_basenames)' -d 'Project'
end

# Open single AI coding agent window (without Zellij)
# Delegates to hive run for agent detection and execution
function acc --description 'Open single AI coding agent window'
    hive run $argv
end

# Kill/delete session
abbr --add -g zk 'zellij kill-session'
abbr --add -g zd 'zellij delete-session'
abbr --add -g zka 'zellij kill-all-sessions'
abbr --add -g zda 'zellij delete-all-sessions'
abbr --add -g zrma 'zellij kill-all-sessions; zellij delete-all-sessions'

# Kill and delete session(s)
function zrm --description 'Kill and delete zellij session(s)'
    if test (count $argv) -eq 0
        echo "Usage: zrm <session-name>..."
        return 1
    end
    for session in $argv
        zellij kill-session $session 2>/dev/null
        zellij delete-session $session
    end
end

# Completions for zrm - suggest existing sessions
complete -c zrm -f -a "(zellij list-sessions -s 2>/dev/null)"

if not type -q tmux
    abbr --add -g tmux zellij
end

# AI Coding Agents - Fish shell integration
#
# This file provides:
# - zc: Open Zellij with auto-detected agent (with optional project jump)
# - zcc, zcu, zcp, zco, zcg: Open Zellij with specific agent layouts
# - acc: Abbreviation for hive run (ai-code equivalent)
# - h: Abbreviation for hive
# - cda: Wrapper for cd to worktree (with completions)
# - gemini: Wrapper for Google Gemini CLI via npx
#
# Core commands are provided by the hive CLI (installed via pipx):
#   hive run     - Run AI coding agent (replaces ai-code)
#   hive zellij  - Open Zellij with agent layout (replaces zc)
#   hive wt      - Manage git worktrees (replaces git-worktree-path)
#
# Requires: hive (installed via pipx), zellij (for zc* commands)
# Optional: claude, agent (cursor), copilot, codex, gemini

# Check for hive at full path since ~/.local/bin may not be in PATH yet
set -l _hive_bin ~/.local/bin/hive

# Abbreviations (always available)
abbr --add -g h 'hive'
abbr --add -g acc 'hive run'

# hive shell completions
if test -x $_hive_bin
    _evalcache $_hive_bin completion fish
end

# Gemini CLI wrapper (via npx, no brew package available)
function gemini --description 'Run Google Gemini CLI'
    npx -y @google/gemini-cli -- $argv
end

# cda wrapper - uses hive wt cd and does cd
# Define unconditionally - hive will be in PATH when function is called
function cda --description 'Quick jump to worktree'
    set -l target_path (hive wt cd $argv)
    and cd $target_path
end

# Completions for cda - suggest available worktrees
complete -c cda -f -a "(hive wt list 2>/dev/null | string split ':' -f 1)" -d "Worktree"

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

# Zellij layout functions - define unconditionally
# They check for dependencies at runtime, not definition time

function zcc --description 'Open zellij with claude agent'
    hive zellij --agent=claude $argv
end

function zcu --description 'Open zellij with cursor agent'
    hive zellij --agent=agent $argv
end

function zcp --description 'Open zellij with copilot agent'
    hive zellij --agent=copilot $argv
end

function zco --description 'Open zellij with codex agent'
    hive zellij --agent=codex $argv
end

function zcg --description 'Open zellij with gemini agent'
    hive zellij --agent=gemini $argv
end

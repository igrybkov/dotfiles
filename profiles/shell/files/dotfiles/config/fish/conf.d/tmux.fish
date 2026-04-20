if not type -q tmux
    return
end

# List sessions
abbr --add -g tls 'tmux list-sessions'

# Attach to a session (fuzzy with completion)
abbr --add -g ta 'tmux attach-session -t'

# Kill specific session(s)
function tk --description 'Kill tmux session(s)'
    if test (count $argv) -eq 0
        echo "Usage: tk <session-name>..."
        return 1
    end
    for session in $argv
        tmux kill-session -t $session
    end
end

# Kill all sessions / the whole tmux server
abbr --add -g tka 'tmux kill-server'

# Completions — suggest existing tmux sessions
complete -c tk -f -a "(tmux list-sessions -F '#{session_name}' 2>/dev/null)"
complete -c ta -f -a "(tmux list-sessions -F '#{session_name}' 2>/dev/null)"

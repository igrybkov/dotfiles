# SSH wrapper to override TERM for compatibility with remote servers
# Ghostty sets TERM=xterm-ghostty which many servers don't have terminfo for
# This forces xterm-256color which is universally supported

function ssh --description 'SSH with TERM override for compatibility' --wraps ssh
    env TERM=xterm-256color command ssh $argv
end

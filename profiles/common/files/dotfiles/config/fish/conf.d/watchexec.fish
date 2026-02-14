# watchexec abbreviations
# Requires `brew install watchexec`

if type -q watchexec
    # Basic watchexec shortcut
    abbr --add -g we watchexec

    # Watch specific extensions
    abbr --add -g wepy 'watchexec -e py --'
    abbr --add -g wejs 'watchexec -e js,ts --'
    abbr --add -g wemd 'watchexec -e md --'

    # Watch and restart (for long-running processes)
    abbr --add -g wer 'watchexec -r --'

    # Watch and clear screen before each run
    abbr --add -g wec 'watchexec -c --'

    # Watch with debounce (ms)
    abbr --add -g wed 'watchexec -d 500 --'
end

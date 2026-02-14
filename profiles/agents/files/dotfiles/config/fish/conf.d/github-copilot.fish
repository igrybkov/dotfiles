# GitHub Copilot CLI integration
# Uses the new copilot-cli (brew install copilot-cli)
# Run 'copilot auth' to authenticate

if type -q copilot
    # Aliases for quick access
    alias cps='copilot suggest'
    alias cpe='copilot explain'

    # Suggest a shell command (interactive)
    function copilot-suggest
        set -l query (string join " " $argv)
        if test -n "$query"
            copilot suggest "$query"
        else
            copilot suggest
        end
    end

    # Explain command from clipboard
    function copilot-explain-clipboard
        set -l cmd (pbpaste)
        if test -n "$cmd"
            echo "Explaining: $cmd"
            copilot explain "$cmd"
        else
            echo "Clipboard is empty"
        end
    end

    # Keybinding: Ctrl+G Ctrl+S to suggest (in command mode)
    # Type your intent, press the keybinding
    function _copilot_suggest_from_buffer
        set -l cmd (commandline)
        if test -n "$cmd"
            commandline -r ""
            copilot suggest "$cmd"
            commandline -f repaint
        else
            copilot suggest
        end
    end

    bind \cg\cs _copilot_suggest_from_buffer
end

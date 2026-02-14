if not type -q pbcopy or not type -q pbpaste
    return
end

abbr -a CP --position anywhere --set-cursor "| pbcopy"
abbr -a PC --position anywhere --set-cursor "| pbcopy"
abbr -a PB --position command --set-cursor "pbpaste | %"

function pbtmp --description "Copy the contents of the clipboard to a temporary file and copy the file path to the clipboard"
    set -l tmpfile (mktemp)
    pbpaste > $tmpfile
    echo -n $tmpfile | pbcopy
    echo "Clipboard contents saved to: $tmpfile (path copied to clipboard)"
end

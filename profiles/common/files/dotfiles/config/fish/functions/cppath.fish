# Copy full path to clipboard
# Usage: cppath <file>
#        cppath (copies current directory)

function cppath --description 'Copy full path to clipboard'
    if test (count $argv) -eq 0
        # No argument - copy current directory
        set -l path (pwd)
        echo -n $path | pbcopy
        echo "Copied: $path"
    else
        # Resolve to absolute path
        set -l path (realpath $argv[1] 2>/dev/null)
        if test $status -ne 0
            echo "Error: '$argv[1]' does not exist" >&2
            return 1
        end
        echo -n $path | pbcopy
        echo "Copied: $path"
    end
end

# Fuzzy cd with fzf
function fcd
    if not type -q fzf
        echo "fzf is not installed, cannot search for subdirectory"
        return 1
    end
    if type -q eza
        set -l tree_cmd 'eza --tree --level=2 --color=always --icons'
    else if type -q tree
        set -l tree_cmd 'tree -C -L 2'
    end
    if test -n "$tree_cmd"
        set -l preview_cmd "--preview '$tree_cmd {} | head -100'"
    end
    set -l all_dirs (find * -type d)
    set -l target_dir (printf '%s\n' $all_dirs | fzf --query="$argv" --scheme=path --height 40% --layout=reverse --prompt 'Select subdirectory: ' --select-1 --exit-0 $preview_cmd)
    set -l fzf_status $status
    if test $fzf_status -eq 0
        if test -n "$target_dir"
            cd $target_dir
            return 0
        end
        echo "fcd: no directory selected"
        return 1
    else if test $fzf_status -eq 130
        echo "fcd: operation cancelled"
        return 1
    else if test $fzf_status -eq 1
        echo "fcd: no matching directory found"
        return 1
    end
    echo "fcd: unknown error"
    return 1
end

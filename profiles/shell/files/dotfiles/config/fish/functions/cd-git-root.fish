function cd-git-root
    argparse 'f/fuzzy' -- $argv
    or return

    if git rev-parse --show-toplevel >/dev/null 2>&1
        cd (git rev-parse --show-toplevel)
        if test (count $argv) -eq 0 -a -z "$_flag_fuzzy"
            return
        end
        set -l search_dir $argv[1]
        # If the directory exists, cd into it
        if test -d $search_dir
            cd $search_dir
            return
        end
        # If fcd is available, use it to fuzzy find the directory
        if type -q fcd
            fcd $argv
            return $status
        # If fzf is available, use it to fuzzy find the directory
        else if type -q fzf
            if type -q eza
                set -l tree_cmd 'eza --tree --level=2 --color=always --icons'
            else
                set -l tree_cmd 'tree -C -L 2'
            end
            if test -n "$tree_cmd"
                set -l preview_cmd "--preview '$tree_cmd {} | head -100'"
            end
            set -l target_dir (find * -type d | fzf --query="$argv" --scheme=path --height 40% --layout=reverse --prompt 'Select subdirectory: ' --select-1 --exit-0 $preview_cmd)
            if test $status -ne 0
                return 1
            end
            if test -n "$target_dir"
                cd $target_dir
                return
            end
            return 1
        end
        echo "fzf is not installed, cannot search for subdirectory"
        return 1
    else
        echo "Not in a git repository"
        return 1
    end
end

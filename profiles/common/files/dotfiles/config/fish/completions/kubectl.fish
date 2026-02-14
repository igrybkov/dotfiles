function __kubectl_generate_completions
    if not type -q kubectl
        return
    end

    if type -q fzf
        kubectl completion fish | sed 's#-a \'\$__kubectl_comp_results\'$#-a \'(printf "%s\\\n" $__kubectl_comp_results | fzf --multi=0 --bind "tab:down" --height 40% --layout=reverse --select-1 --exit-0 )\'#g'
    else
        kubectl completion fish
    end
end

if type -q _evalcache
    _evalcache __kubectl_generate_completions 2>&1 &> /dev/null
else
    __kubectl_generate_completions | source
end

# Remove the temporary function from the namespace
functions --erase __kubectl_generate_completions

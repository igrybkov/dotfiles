if status is-interactive
    # zoxide initialization
    if type -q zoxide
        _evalcache zoxide init fish | source
    end
end

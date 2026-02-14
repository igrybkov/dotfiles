if not type -q k9s
    return
end

if type -q _evalcache
    _evalcache k9s completion fish
else
    k9s completion fish | source
end

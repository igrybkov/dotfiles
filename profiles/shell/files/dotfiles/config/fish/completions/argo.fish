if not type -q argo
    return
end

if type -q _evalcache
    _evalcache argo completion fish 2>&1 &> /dev/null
else
    argo completion fish | source
end

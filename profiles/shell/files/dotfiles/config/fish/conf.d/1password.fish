if type -q op
    _evalcache op completion fish
end

# Import plugins
if test -f ~/.config/op/plugins.sh
    source ~/.config/op/plugins.sh
end

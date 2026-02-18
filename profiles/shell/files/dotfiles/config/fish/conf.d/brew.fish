if test -x /opt/homebrew/bin/brew
    _evalcache /opt/homebrew/bin/brew shellenv
else if type -q brew
    _evalcache brew shellenv
end

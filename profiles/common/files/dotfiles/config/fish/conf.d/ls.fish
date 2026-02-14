# `ls` → `exa` alias
# Requires `brew install exa`
if type -q eza
    # abbr --add -g ls 'eza --long --classify --all --header --git --no-user --tree --level 1'
    alias ls 'eza -gh -s=type --git'
    if not type -q tree
        abbr --add -g tree 'eza -gh -s=type --git --tree'
    end
end

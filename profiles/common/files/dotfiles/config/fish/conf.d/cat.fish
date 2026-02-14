# `cat` → `bat` abbreviation
# Requires `brew install bat`

if type -q bat
    abbr -a c 'bat'
    abbr -a b 'bat'
    abbr -a cat bat
    abbr -a L --position anywhere --set-cursor "% | bat --style=header,grid --color=always"
else
    abbr -a c 'cat'
    abbr -a b 'cat'
end

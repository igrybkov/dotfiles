set -l grep_cmd "grep --color=always '%'"
set -l grep_regex_cmd "grep --color=always -E '%'"
if type -q rg
    set grep_cmd "rg --color=always '%'"
    set grep_regex_cmd "rg --color=always -E '%'"
end
abbr -a G --position anywhere --set-cursor "| $grep_cmd"
abbr -a RG --position anywhere --set-cursor "| $grep_regex_cmd"

# Description: Add abbreviations to cd up multiple directories
for i in (seq 9)
    set -l path (string repeat -n $i "../")
    abbr --add -g "..$i" "cd $path"
    abbr --add -g "..$i/" "cd $path"
    if test $i -gt 1
        # add abbreviations to match ... to .. 3, .... to .. 4, etc
        set -l dots (string repeat -n (math $i + 1) ".")
        abbr --add -g "$dots" "cd $path"
    end
end

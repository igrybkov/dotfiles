# Hand-maintained until click ships a working fish template.
# Click >=8.4 renders `string split \n` in its source template as a literal
# newline (the template uses a regular Python string), producing a fish script
# that fails to parse. Each completion item is also emitted as three lines
# (type, value, help) — `set -l response (cmd)` flattens those across items,
# so we walk the list in 3-line strides instead of splitting per-element.
function _dotfiles_completion
    set -l response (env _DOTFILES_COMPLETE=fish_complete COMP_WORDS=(commandline -cp) COMP_CWORD=(commandline -t) dotfiles)
    set -l n (count $response)
    set -l i 1
    while test $i -le (math $n - 2)
        set -l type $response[$i]
        set -l value $response[(math $i + 1)]
        set -l help $response[(math $i + 2)]
        switch $type
            case dir
                __fish_complete_directories $value
            case file
                __fish_complete_path $value
            case plain
                if test "$help" = "_"
                    echo $value
                else
                    printf "%s\t%s\n" $value $help
                end
        end
        set i (math $i + 3)
    end
end

complete --no-files --command dotfiles --arguments "(_dotfiles_completion)"

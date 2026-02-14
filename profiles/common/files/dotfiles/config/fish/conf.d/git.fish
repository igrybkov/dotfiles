# Add git aliases as abbreviations

abbr --add -g g git

if type -q lazygit
    abbr --add -g lg lazygit
    abbr --add -g lgl "lazygit log"
    abbr --add -g lgb "lazygit branch"
    abbr --add -g lgs "lazygit status"
    abbr --add -g lgstash "lazygit stash"
end

# Parse git aliases and create fish abbreviations using native string commands
for line in (git config --get-regexp '^alias\.')
    # Extract alias name: "alias.foo bar baz" -> "foo"
    set -l alias_name (string replace -r '^alias\.([a-zA-Z0-9\-]+)\s.*' '$1' -- $line)
    # Extract alias value: "alias.foo bar baz" -> "bar baz"
    set -l alias_value (string replace -r '^alias\.[a-zA-Z0-9\-]+\s+' '' -- $line)

    # Skip if extraction failed
    if test -z "$alias_name" -o -z "$alias_value"
        continue
    end

    # Check if it's a shell command alias (starts with !)
    if string match -q '!*' -- $alias_value
        # if it's a complex alias that's a shell command, we're not going to expand it
        set alias_value $alias_name
    else
        # expand the alias value to the full command for git cli
        abbr --add -g --command git "$alias_name" "$alias_value"
    end

    # Check if there is a command or an abbreviation with the same name as the alias
    if not type -q "g$alias_name"; and not abbr -q "g$alias_name"
        # if there's no conflict, let's add the alias
        abbr --add -g "g$alias_name" "git $alias_value"
    end
end

if type -q cd-git-root
    # If the cd-git-root function is available, add abbreviations for it
    abbr --add -g cdgr cd-git-root
    abbr --add -g cdr cd-git-root
    abbr --add -g cdgrf 'cd-git-root --fuzzy'
end

# Add git aliases as abbreviations

abbr --add -g g git

if type -q lazygit
    abbr --add -g lg lazygit
    abbr --add -g lgl "lazygit log"
    abbr --add -g lgb "lazygit branch"
    abbr --add -g lgs "lazygit status"
    abbr --add -g lgstash "lazygit stash"
end

# Lookup table for position-aware git alias expansion
set -g _git_abbr_expansions

# Only expand git aliases in first-arg position so that e.g.
# 'git remove' → 'git remote' but 'git worktree remove' stays unchanged
function _git_abbr_positional
    set -l tokens (commandline -op)
    set -l token $tokens[-1]
    if test (count $tokens) -le 2
        for entry in $_git_abbr_expansions
            if string match -q -- "$token=*" $entry
                string replace -- "$token=" '' $entry
                return
            end
        end
    end
    echo $token
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
        # Register in lookup table and create position-aware abbreviation
        set -a _git_abbr_expansions "$alias_name=$alias_value"
        abbr --add -g --command git --function _git_abbr_positional -- "$alias_name"
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

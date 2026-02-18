# Add GitHub CLI abbreviations

if type -q gh
    # Switch GitHub authentication to github.com
    abbr --add -g ghas 'gh auth switch -h github.com'
    # Shortcut for switching GitHub accounts
    abbr --add -g --command gh account 'auth switch'
end

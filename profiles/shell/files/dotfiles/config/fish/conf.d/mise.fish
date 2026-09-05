if type -q mise
    _evalcache mise activate fish | source

    # mise hits GitHub's unauthenticated API rate limit (60/hr, shared across
    # the whole network) when resolving "latest"/release info. Export
    # GITHUB_TOKEN from the already-authenticated gh CLI, but only lazily on
    # first actual `mise` invocation, not on every shell startup.
    function mise --wraps mise --description 'mise, with GITHUB_TOKEN set from gh to avoid API rate limits'
        if not set -q GITHUB_TOKEN; and type -q gh; and gh auth status >/dev/null 2>&1
            set -gx GITHUB_TOKEN (gh auth token)
        end
        command mise $argv
    end
end

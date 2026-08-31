if status is-interactive
    # zoxide initialization
    if type -q zoxide
        # Work around fish 4.8+ no longer shipping functions/cd.fish on disk
        # (builtins are now embedded in the binary), which makes zoxide's
        # init script emit a harmless but noisy warning when it tries to
        # read that file. Pre-define __zoxide_cd_internal from the live
        # `cd` function so zoxide's script finds it already defined.
        # https://github.com/ajeetdsouza/zoxide/issues/1272
        if not builtin functions --query __zoxide_cd_internal
            functions cd | string replace --regex -- '^function cd\s' 'function __zoxide_cd_internal ' | source
        end
        _evalcache zoxide init fish | source
    end
end

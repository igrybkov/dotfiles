# Create a "k<group>-all" function that runs a kubectl command across all aliases in the group.
# Example usage:
#   __kubectl_add_group "bb" "bbd" "bbs" "bbpva6" "bbpva7"
# This creates "kbb-all" so that "kbb-all rollout restart deployment" runs:
#   kbbd rollout restart deployment
#   kbbs rollout restart deployment
#   kbbpva6 rollout restart deployment
#   kbbpva7 rollout restart deployment
function __kubectl_add_group
    if test (count $argv) -lt 2
        echo "Usage: __kubectl_add_group GROUP_NAME ALIAS [ALIAS...]" >&2
        return 1
    end

    set -l group_name $argv[1]
    set -l aliases $argv[2..-1]
    set -g __kubectl_group_$group_name $aliases

    function k$group_name-all -V group_name
        set -l group_var __kubectl_group_$group_name
        for _alias in $$group_var
            echo "==> k$_alias"
            k$_alias $argv
            echo
        end
    end
end

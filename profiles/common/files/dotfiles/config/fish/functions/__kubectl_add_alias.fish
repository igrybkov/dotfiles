# Shell command that adds aliases for kubectl.
# This function will create aliases for kubectl with the specified names prefixed with "k" and options.
# Example usage:
#   __kubectl_add_alias "--context=my-cluster --namespace=my-ns" my-cluster mc
# This will create aliases "kmy-cluster" and "kmc" that run "kubectl --context=my-cluster --namespace=my-ns".
# If k9s is installed, it will also create aliases "kkmy-cluster" and "kkmc" for k9s.
function __kubectl_add_alias
    if test (count $argv) -lt 2
        echo "Usage: __kubectl_add_alias OPTIONS ALIAS [ALIAS...]" >&2
        return 1
    end

    set -l options $argv[1]
    set -l aliases $argv[2..-1]

    for alias_name in $aliases
        alias "k$alias_name" "kubectl $options"
        if type -q k9s
            alias "kk$alias_name" "k9s $options"
        end
    end
end

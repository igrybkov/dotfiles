# Shell command that adds aliases for kubectl.
# This function will create aliases for kubectl with the specified names prefixed with "k" and options.
# Example usage:
#   __kubectl_add_alias "--context=my-cluster --namespace=my-ns" my-cluster mc
# This will create aliases "kmy-cluster" and "kmc" that run "kubectl --context=my-cluster --namespace=my-ns".
# If k9s is installed, it will also create aliases "kkmy-cluster" and "kkmc" for k9s.
# Pass --argo to also create "argo-<alias>" aliases for the argo CLI:
#   __kubectl_add_alias --argo "--context=my-cluster --namespace=argo" my-cluster mc
function __kubectl_add_alias
    set -l argo false
    set -l args

    for arg in $argv
        if test "$arg" = --argo
            set argo true
        else
            set -a args $arg
        end
    end

    if test (count $args) -lt 2
        echo "Usage: __kubectl_add_alias [--argo] OPTIONS ALIAS [ALIAS...]" >&2
        return 1
    end

    set -l options $args[1]
    set -l aliases $args[2..-1]

    for alias_name in $aliases
        alias "k$alias_name" "kubectl $options"
        if type -q k9s
            alias "kk$alias_name" "k9s $options"
        end
        if test "$argo" = true; and type -q argo
            set -l argo_alias (string replace -r '^-' '' -- $alias_name)
            alias "argo-$argo_alias" "argo $options"
        end
    end
end

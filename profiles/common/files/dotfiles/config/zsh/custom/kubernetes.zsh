#shellcheck disable=SC2148
if command -v kubectl 1>/dev/null 2>&1; then
  function kube-contexts-reload() {
    # Set the default kube context if present
    local DEFAULT_KUBE_CONTEXTS="$HOME/.kube/config"
    if test -f "${DEFAULT_KUBE_CONTEXTS}"; then
      export KUBECONFIG="$DEFAULT_KUBE_CONTEXTS"
    fi

    # Additional contexts should be in ~/.kube/*.yml
    CUSTOM_KUBE_CONTEXTS="$HOME/.kube"
    mkdir -p "${CUSTOM_KUBE_CONTEXTS}"

    OIFS="$IFS"
    IFS=$'\n'
    # shellcheck disable=SC2044
    for contextFile in $(find "${CUSTOM_KUBE_CONTEXTS}" -maxdepth 1 -type f -name "*.yml"); do
      echo "Adding kube context: $contextFile"
      export KUBECONFIG="$contextFile:$KUBECONFIG"
    done
    IFS="$OIFS"
  }

  if [ -z "${_comps[kubectl]}" ]; then
    _evalcache_autocomplete kubectl completion zsh
  fi

  kube-contexts-reload >/dev/null

  if command -v kubecolor &>/dev/null; then
    alias kubectl="kubecolor"
    compdef _kubectl kubecolor
  fi

  alias k=kubectl
fi

if command -v flux &>/dev/null; then
  if [ -z "${_comps[flux]}" ]; then
    _evalcache_autocomplete flux completion zsh
  fi
fi

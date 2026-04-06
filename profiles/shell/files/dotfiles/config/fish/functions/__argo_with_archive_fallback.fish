# Wrapper around the argo CLI that falls back to archived workflows when a live
# workflow is not found. Used by the argo-* aliases created in __kubectl_add_alias.
function __argo_with_archive_fallback
    # Split into argo base options and the user subcommand + args.
    # Base options come first (flags like --context, --namespace).
    set -l base_options
    set -l rest

    set -l parsing_base true
    for arg in $argv
        if $parsing_base
            switch $arg
                case '--*=*'
                    set -a base_options $arg
                case '--*'
                    # Peek: this flag may take a value as the next arg
                    set -a base_options $arg
                case '-*'
                    set -a base_options $arg
                case '*'
                    # First non-flag after base options might be a value for the
                    # previous flag (e.g. --context VALUE). Detect by checking if
                    # the last base option looks like it expects a value.
                    if set -q base_options[-1]; and string match -qr -- '^--(context|namespace|kubeconfig|server|cluster|user)$' $base_options[-1]
                        set -a base_options $arg
                    else
                        set parsing_base false
                        set -a rest $arg
                    end
            end
        else
            set -a rest $arg
        end
    end

    # Try the command directly first
    set -l output (argo $base_options $rest 2>&1)
    set -l exit_code $status

    if test $exit_code -eq 0
        printf '%s\n' $output
        return 0
    end

    # Check if the error is a "not found" error
    if not string match -q '*not found*' "$output"
        printf '%s\n' $output >&2
        return $exit_code
    end

    # Extract subcommand and workflow name from rest args
    set -l subcmd $rest[1]
    set -l wf_name $rest[2]

    if test -z "$wf_name"
        printf '%s\n' $output >&2
        return $exit_code
    end

    echo "Workflow '$wf_name' not found in live workflows, searching archive..." >&2

    # Look up the workflow UID from the archive
    set -l ns_flag
    for i in (seq (count $base_options))
        if test "$base_options[$i]" = --namespace; or test "$base_options[$i]" = -n
            set ns_flag $base_options[(math $i + 1)]
            break
        else if string match -qr -- '^--(namespace|n)=(.+)$' $base_options[$i]
            set ns_flag (string replace -r -- '^--(?:namespace|n)=' '' $base_options[$i])
            break
        end
    end

    set -l archive_opts $base_options
    # argo archive list -o json may return an array or {"items":[...]}
    set -l uid (argo archive list $archive_opts -o json 2>/dev/null \
        | command jq -r --arg name "$wf_name" '
            (if type == "array" then . elif .items then .items else [] end)
            | map(select(.metadata.name == $name))
            | first
            | .metadata.uid // empty
        ' 2>/dev/null \
        | head -1)

    if test -z "$uid"
        echo "Workflow '$wf_name' not found in archive either." >&2
        printf '%s\n' $output >&2
        return $exit_code
    end

    echo "Found archived workflow UID: $uid" >&2

    switch $subcmd
        case logs
            # For logs, use `argo archive get` in YAML and extract log info,
            # or try kubectl logs if pods still exist
            set -l remaining_args $rest[3..-1]
            # Attempt to get logs via kubectl from the workflow's pods
            set -l pod_names (argo archive get $uid $archive_opts -o json 2>/dev/null \
                | command jq -r '.status.nodes // {} | to_entries[] | select(.value.type == "Pod") | .value.id' 2>/dev/null)

            set -l k_opts
            for i in (seq (count $base_options))
                if test "$base_options[$i]" = --context
                    set -a k_opts --context $base_options[(math $i + 1)]
                else if string match -qr -- '^--context=(.+)$' $base_options[$i]
                    set -a k_opts $base_options[$i]
                else if test "$base_options[$i]" = --namespace -o "$base_options[$i]" = -n
                    set -a k_opts --namespace $base_options[(math $i + 1)]
                else if string match -qr -- '^--(namespace|n)=(.+)$' $base_options[$i]
                    set -a k_opts $base_options[$i]
                end
            end

            if test (count $pod_names) -gt 0
                for pod in $pod_names
                    echo "--- Logs for pod: $pod ---" >&2
                    kubectl $k_opts logs $pod -c main $remaining_args 2>/dev/null
                    or echo "(pod $pod logs not available)" >&2
                end
            else
                echo "No pod logs available. Showing archived workflow info:" >&2
                argo archive get $uid $archive_opts
            end
        case get
            argo archive get $uid $archive_opts $rest[3..-1]
        case '*'
            # For other subcommands, no archive fallback — show original error
            printf '%s\n' $output >&2
            return $exit_code
    end
end

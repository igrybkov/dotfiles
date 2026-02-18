function find_in_parent_folders --argument-names filename
    set -l current_dir (pwd)

    while test $current_dir != ""
        if test -e $current_dir/$filename
            echo $current_dir/$filename
            return 0
        end
        if test $current_dir = "/"
            return 1
        end
        set current_dir (dirname $current_dir)
    end
    return 1
end

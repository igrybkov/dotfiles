if type -q make
    function make --wraps make
        # Make
        if [ -f Makefile ] || [ -f makefile ]
            # If Makefile exists, use the make command
            command make $argv
        else
            # check if Makefile exists in gitroot
            set -l gitroot (git rev-parse --show-toplevel 2>/dev/null)
            if [ -f "$gitroot/Makefile" ] || [ -f "$gitroot/makefile" ]
                # If Makefile exists in gitroot, use the make command
                command make -C $gitroot $argv
            end
            # If Makefile does not exist, print an error message
            return 1
        end
    end
end

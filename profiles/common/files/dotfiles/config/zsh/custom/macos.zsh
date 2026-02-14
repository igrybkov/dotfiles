#shellcheck disable=SC1107,SC1091,SC2148
# Empty the Trash on all mounted volumes and the main HDD
# Also, clear Apple’s System Logs to improve shell startup speed
alias emptytrash="sudo rm -rfv /Volumes/*/.Trashes; sudo rm -rfv ~/.Trash; sudo rm -rfv /private/var/log/asl/*.asl"

# VLC alias
alias vlc="/Applications/VLC.app/Contents/MacOS/VLC"

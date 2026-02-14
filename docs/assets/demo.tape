# VHS demo recording for dotfiles README
# Generate with: vhs docs/assets/demo.tape
# Prerequisites: brew install charmbracelet/tap/vhs ffmpeg ttyd

Output docs/assets/demo.gif

Set Shell bash
Set Width 1200
Set Height 800
Set FontSize 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set Padding 20

# Enable demo mode to hide private profiles
Env DEMO "1"

# Show CLI help
Type "dotfiles --help"
Enter
Sleep 3s
Hide
Type "clear"
Enter
Show

# Show install help
Type "dotfiles install --help"
Enter
Sleep 3s
Hide
Type "clear"
Enter
Show

# Show available profiles
Type "dotfiles profile list"
Enter
Sleep 3s

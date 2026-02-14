# VHS demo recording for dotfiles README
# Generate with: vhs docs/assets/demo.tape
# Prerequisites: brew install charmbracelet/tap/vhs ffmpeg ttyd

Output docs/assets/demo.gif

Set Shell bash
Set Width 1200
Set Height 600
Set FontSize 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 50ms
Set Padding 20

# Show CLI help
Type "dotfiles --help"
Enter
Sleep 3s

# Show install help
Type "dotfiles install --help"
Enter
Sleep 3s

# Show available profiles
Type "dotfiles profile list"
Enter
Sleep 3s

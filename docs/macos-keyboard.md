# macOS Keyboard Setup

Manual keyboard configuration is required - automation via `defaults write` to HIToolbox is fragile and can corrupt language settings after reboot.

## Keyboard Layouts

Configure in: **System Settings > Keyboard > Input Sources**

| Layout | Purpose |
|--------|---------|
| U.S. | Primary English layout |
| Ukrainian | Cyrillic layout |

## Input Source Switching

Set up **Option+Space** to switch between layouts:

1. Go to **System Settings > Keyboard > Keyboard Shortcuts > Input Sources**
2. Enable "Select the previous input source"
3. Set shortcut to **⌥Space** (Option+Space)

Alternatively, use "Select next source in input menu" if you prefer cycling forward.

## Why Not Automated?

Keyboard layout configuration via `defaults write com.apple.HIToolbox AppleEnabledInputSources` is problematic:

- macOS caches these settings in complex ways
- The plist format is fragile and undocumented
- Changes can corrupt settings that only manifest after reboot
- The relationship between keyboard layouts, input sources, and system languages is tightly coupled

It's safer to configure this once manually through System Settings.

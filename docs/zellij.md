# Zellij Usage Guide

This guide documents the Zellij terminal multiplexer configuration and usage, including integration with Neovim.

## Overview

Zellij is a terminal workspace with batteries included. This configuration uses:
- **Custom keybindings** with `clear-defaults=true`
- **Autolock plugin** for seamless Neovim integration
- **zellij-nav.nvim** for unified pane/tab navigation from Neovim

## Modes

Zellij operates in different modes. Press the mode key to enter, `Esc` or `Enter` to exit back to normal.

| Mode | Enter Key | Purpose |
|------|-----------|---------|
| Normal | (default) | Standard operation |
| Locked | `Ctrl+g` | Pass all keys to terminal |
| Pane | `Ctrl+p` | Pane management |
| Tab | `Ctrl+t` | Tab management |
| Resize | `Ctrl+n` | Resize panes |
| Move | `Ctrl+h` | Move panes |
| Scroll | `Ctrl+s` | Scroll/search buffer |
| Session | `Ctrl+o` | Session management |
| Tmux | `Ctrl+b` | Tmux-compatible bindings |

## Autolock Plugin

The autolock plugin automatically switches to **Locked** mode when running certain applications:
- `nvim`, `vim` - Editors
- `git` - Git operations (interactive rebase, etc.)
- `fzf` - Fuzzy finder
- `zoxide` - Directory jumper
- `atuin` - Shell history

When you exit these applications, Zellij automatically returns to **Normal** mode.

### Manual Override

| Key | Action |
|-----|--------|
| `Alt+z` (in Normal) | Disable autolock and switch to Locked |
| `Alt+z` (in Locked) | Enable autolock and switch to Normal |
| `Alt+Shift+z` | Enable autolock |

## Global Keybindings (shared_except "locked")

These work in all modes except Locked:

| Key | Action |
|-----|--------|
| `Alt+h` | Move focus left (or prev tab) |
| `Alt+j` | Move focus down |
| `Alt+k` | Move focus up |
| `Alt+l` | Move focus right (or next tab) |
| `Alt+n` | New pane |
| `Alt+f` | Toggle floating panes |
| `Alt+[` | Previous swap layout |
| `Alt+]` | Next swap layout |
| `Alt+i` | Move tab left |
| `Alt+o` | Move tab right |
| `Ctrl+q` | Quit Zellij |

## Pane Mode (`Ctrl+p`)

| Key | Action |
|-----|--------|
| `h/j/k/l` or arrows | Move focus |
| `n` | New pane |
| `d` | New pane down |
| `r` | New pane right |
| `s` | New stacked pane |
| `x` | Close pane |
| `f` | Toggle fullscreen |
| `w` | Toggle floating |
| `e` | Toggle embed/floating |
| `z` | Toggle pane frames |
| `c` | Rename pane |
| `p` | Switch focus |

## Tab Mode (`Ctrl+t`)

| Key | Action |
|-----|--------|
| `h/l` or arrows | Navigate tabs |
| `n` | New tab |
| `x` | Close tab |
| `r` | Rename tab |
| `1-9` | Go to tab N |
| `b` | Break pane to new tab |
| `[` | Break pane left |
| `]` | Break pane right |
| `s` | Toggle sync |
| `Tab` | Toggle last tab |

## Resize Mode (`Ctrl+n`)

| Key | Action |
|-----|--------|
| `h/j/k/l` | Increase size in direction |
| `H/J/K/L` | Decrease size in direction |
| `+/=` | Increase size |
| `-` | Decrease size |

## Scroll Mode (`Ctrl+s`)

| Key | Action |
|-----|--------|
| `j/k` | Scroll down/up |
| `d/u` | Half page down/up |
| `Ctrl+f/b` | Page down/up |
| `s` | Enter search mode |
| `e` | Edit scrollback in `$EDITOR` |

## Session Mode (`Ctrl+o`)

| Key | Action |
|-----|--------|
| `d` | Detach |
| `w` | Session manager |
| `c` | Configuration |
| `p` | Plugin manager |
| `a` | About |

## Tmux Mode (`Ctrl+b`)

For tmux muscle memory:

| Key | Action |
|-----|--------|
| `"` | Split horizontal |
| `%` | Split vertical |
| `c` | New tab |
| `n/p` | Next/prev tab |
| `z` | Toggle fullscreen |
| `d` | Detach |
| `[` | Scroll mode |

---

# Neovim Integration

## zellij-nav.nvim

This plugin provides seamless navigation between Neovim windows and Zellij panes. It works **even when Zellij is locked** because it communicates directly via the Zellij CLI.

### Keybindings (from Neovim)

| Key | Action |
|-----|--------|
| `Ctrl+h` | Navigate left (or previous tab at edge) |
| `Ctrl+j` | Navigate down |
| `Ctrl+k` | Navigate up |
| `Ctrl+l` | Navigate right (or next tab at edge) |

### How It Works

1. When you press `Ctrl+h` in Neovim:
   - If there's a Neovim split to the left → move to it
   - If at the edge → tell Zellij to move focus left
   - If no Zellij pane to the left → switch to previous tab

2. The autolock plugin keeps Zellij locked while in Neovim
3. zellij-nav.nvim bypasses the lock by using `zellij action` CLI commands

### Workflow Example

```
┌─────────────────────────────────────────────────┐
│ Tab 1: Code                                     │
├──────────────────────┬──────────────────────────┤
│                      │                          │
│   Neovim (locked)    │   Terminal (unlocked)   │
│                      │                          │
│  Ctrl+l →            │  ← Alt+h                │
│                      │                          │
└──────────────────────┴──────────────────────────┘
```

- In Neovim: Use `Ctrl+h/j/k/l` to navigate
- In Terminal: Use `Alt+h/j/k/l` or enter a mode first

---

# Tips & Tricks

## Quick Actions

- **New pane**: `Alt+n`
- **Toggle floating**: `Alt+f`
- **Fullscreen pane**: `Ctrl+p` then `f`
- **Close pane**: `Ctrl+p` then `x`

## Session Management

```bash
# List sessions
zellij list-sessions

# Attach to session
zellij attach <session-name>

# Create named session
zellij --session my-project

# Delete session
zellij delete-session <session-name>
```

## Layouts

Layouts are stored in `~/.config/zellij/layouts/`. Start with a layout:

```bash
zellij --layout my-layout
```

## Troubleshooting

### Keys not working in Neovim

1. Check if Zellij is locked: Look at the status bar
2. Ensure zellij-nav.nvim is installed and loaded
3. Verify autolock triggers include your application

### Autolock not working

1. Restart Zellij (plugin changes require restart)
2. Check that the autolock plugin loaded: `Ctrl+o` -> `p` (plugin manager)
3. Verify triggers in config match your command names

---

# Plugin Management

Zellij plugins are configured directly in `~/.config/zellij/config.kdl` using pinned `https://` URLs. Zellij caches plugins automatically.

**Important:** Never use `https://` URLs with `/latest/` in Zellij plugin locations. All plugins must be pinned to specific versions to ensure controlled updates.

## Plugin Configuration

**Config location:** `profiles/common/files/dotfiles/config/zellij/config.kdl`

```kdl
plugins {
    autolock location="https://github.com/fresh2dev/zellij-autolock/releases/download/0.2.2/zellij-autolock.wasm" { ... }
}
```

## Adding a New Plugin

1. Find the plugin's GitHub releases page and get the URL for a specific version (not `latest`)
2. Add the plugin alias to `config.kdl`
3. Add keybindings if needed
4. Restart Zellij (plugin will be downloaded and cached automatically)

## Updating a Plugin

1. Update the version in the URL in `config.kdl`
2. Restart Zellij (new version will be downloaded and cached)

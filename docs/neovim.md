# Neovim Usage Guide

This guide documents the Neovim configuration and installed plugins.

## Overview

This configuration uses:
- **lazy.nvim** - Plugin manager with lazy loading
- **Native LSP** (Neovim 0.11+) - Built-in language server support
- **File-per-plugin pattern** - Each plugin in its own file under `lua/lazy_plugins/`

## Quick Reference

| Key | Action |
|-----|--------|
| `<C-n>` | Toggle file tree |
| `<leader>ff` | Find files |
| `<leader>fg` | Live grep |
| `<leader>cf` | Format buffer |
| `<C-l>` (insert) | Accept Copilot suggestion |
| `<C-h/j/k/l>` | Navigate Zellij panes/tabs |

---

## Plugins

### File Explorer (nvim-tree)

File tree explorer that opens automatically on startup.

| Key | Action |
|-----|--------|
| `<C-n>` | Toggle tree |

**In the tree:**

| Key | Action |
|-----|--------|
| `Enter` | Open file/expand folder |
| `o` | Open file |
| `<C-v>` | Open in vertical split |
| `<C-x>` | Open in horizontal split |
| `<C-t>` | Open in new tab |
| `a` | Create file/directory |
| `d` | Delete |
| `r` | Rename |
| `x` | Cut |
| `c` | Copy |
| `p` | Paste |
| `y` | Copy name |
| `Y` | Copy relative path |
| `gy` | Copy absolute path |
| `R` | Refresh |
| `H` | Toggle hidden files |
| `I` | Toggle gitignore |
| `q` | Close tree |
| `?` | Help |

**Configuration:**
- Width: 30 columns
- Shows dotfiles (hidden files)
- Case-sensitive sorting
- Groups empty directories

---

### Fuzzy Finder (Telescope)

Powerful fuzzy finder for files, grep, buffers, and more.

| Key | Action |
|-----|--------|
| `<leader>ff` | Find files |
| `<leader>fg` | Live grep (search in files) |
| `<leader>fb` | Open buffers |
| `<leader>fh` | Help tags |
| `<leader>fr` | Recent files |
| `<leader>fc` | Commands |
| `<leader>fs` | Grep string under cursor |

**Inside Telescope:**

| Key | Action |
|-----|--------|
| `<C-j>` | Move to next item |
| `<C-k>` | Move to previous item |
| `<CR>` | Open selected |
| `<C-x>` | Open in horizontal split |
| `<C-v>` | Open in vertical split |
| `<C-t>` | Open in new tab |
| `<C-u>` | Scroll preview up |
| `<C-d>` | Scroll preview down |
| `<Esc>` | Close |
| `<C-c>` | Close |

**Features:**
- Shows hidden files in find_files
- Uses fzf-native for faster fuzzy matching
- Truncated path display

---

### Code Formatter (Conform)

Automatic code formatting with format-on-save.

| Key | Action |
|-----|--------|
| `<leader>cf` | Format buffer (terminal) |
| `<D-M-l>` | Format buffer (GUI only: Cmd+Option+L) |

**Configured formatters:**

| Language | Formatter |
|----------|-----------|
| Lua | stylua |
| Python | ruff_format |
| Shell/Bash/Zsh | shfmt (2-space indent) |
| YAML | prettier |
| JSON/JSONC | prettier |

**Format on save:** Enabled with 500ms timeout.

---

### Autocompletion (nvim-cmp)

Intelligent autocompletion with multiple sources.

| Key | Action |
|-----|--------|
| `<Tab>` | Next item / expand snippet / jump |
| `<S-Tab>` | Previous item / jump back |
| `<CR>` | Confirm selection |
| `<C-Space>` | Trigger completion |
| `<C-e>` | Abort completion |
| `<C-b>` | Scroll docs up |
| `<C-f>` | Scroll docs down |

**Completion sources (in priority order):**
1. LSP suggestions
2. Copilot suggestions
3. Snippets (LuaSnip)
4. Buffer words
5. Neovim Lua API
6. File paths

---

### AI Coding Assistant (Copilot)

GitHub Copilot integration for AI-powered suggestions.

| Key | Action |
|-----|--------|
| `<C-l>` (insert mode) | Accept Copilot suggestion |

**Note:** Tab is disabled for Copilot to avoid conflicts with nvim-cmp. Use `<C-l>` to accept suggestions.

**Other Copilot commands:**
- `:Copilot enable` - Enable Copilot
- `:Copilot disable` - Disable Copilot
- `:Copilot status` - Check status
- `:Copilot panel` - Open suggestions panel

---

### Syntax Highlighting (Treesitter)

Advanced syntax highlighting and code understanding.

**Installed languages:**
- c
- lua
- vim, vimdoc
- elixir
- javascript, typescript
- html
- python

**Features:**
- Syntax highlighting
- Smart indentation
- Incremental selection

**Commands:**
- `:TSUpdate` - Update parsers
- `:TSInstall <lang>` - Install a language parser
- `:TSInstallInfo` - Show installed parsers

---

### Language Server Protocol (LSP)

Native Neovim 0.11+ LSP configuration.

**Configured servers:**
- `html` - HTML language server
- `cssls` - CSS language server

**Default LSP keybindings:**

| Key | Action |
|-----|--------|
| `gd` | Go to definition |
| `gD` | Go to declaration |
| `gi` | Go to implementation |
| `gr` | Go to references |
| `K` | Hover documentation |
| `<C-k>` | Signature help |
| `<leader>rn` | Rename symbol |
| `<leader>ca` | Code action |
| `[d` | Previous diagnostic |
| `]d` | Next diagnostic |

**Adding more LSP servers:**

Edit `lua/lazy_plugins/lspconfig.lua`:
```lua
local servers = { "html", "cssls", "pyright", "ts_ls" }
```

Make sure to install the server (e.g., `npm install -g typescript-language-server`).

---

### Zellij Navigation (zellij-nav.nvim)

Seamless navigation between Neovim and Zellij panes.

| Key | Action |
|-----|--------|
| `<C-h>` | Navigate left (or previous tab) |
| `<C-j>` | Navigate down |
| `<C-k>` | Navigate up |
| `<C-l>` | Navigate right (or next tab) |

**How it works:**
1. If there's a Neovim split in that direction → move to it
2. Otherwise → move to Zellij pane in that direction
3. If no pane → switch to previous/next Zellij tab

Works even when Zellij is in locked mode (autolock).

---

## Plugin Management

### Adding a new plugin

Create a new file in `lua/lazy_plugins/`:

```lua
-- lua/lazy_plugins/my-plugin.lua
return {
  "username/plugin-name",
  event = "VeryLazy",  -- lazy load
  keys = {
    { "<leader>xx", "<cmd>PluginCommand<cr>", desc = "Description" },
  },
  config = function()
    require("plugin-name").setup({
      -- options
    })
  end,
}
```

### Updating plugins

```vim
:Lazy update
```

### Plugin status

```vim
:Lazy
```

---

## Configuration Files

```
~/.config/nvim/
├── init.lua                    # Entry point, loads lazy.nvim
└── lua/
    └── lazy_plugins/           # One file per plugin
        ├── cmp.lua             # Autocompletion
        ├── conform.lua         # Code formatting
        ├── copilot.lua         # GitHub Copilot
        ├── lspconfig.lua       # LSP configuration
        ├── nvim-tree.lua       # File explorer
        ├── telescope.lua       # Fuzzy finder
        ├── treesitter.lua      # Syntax highlighting
        └── zellij-nav.lua      # Zellij integration
```

---

## Tips & Tricks

### Exiting Neovim

| Command | Action |
|---------|--------|
| `:q` | Quit current window |
| `:qa` | Quit all windows |
| `:qa!` | Quit all, discard changes |
| `:w` | Save current file |
| `:wq` | Save and quit |
| `:wqa` | Save all and quit all |
| `ZZ` | Save and quit (normal mode) |
| `ZQ` | Quit without saving (normal mode) |

### Quick file navigation

1. `<C-n>` to open tree, navigate, `Enter` to open
2. `<leader>ff` to fuzzy find by name
3. `<leader>fr` for recent files
4. `<leader>fb` to switch buffers

### Searching in files

1. `<leader>fg` - Live grep (type to search)
2. `<leader>fs` - Search for word under cursor

### Formatting

- Files auto-format on save
- Manual format: `<leader>cf`

### Working with Zellij

- `<C-h/j/k/l>` seamlessly navigates between Neovim splits and Zellij panes
- Autolock keeps Zellij locked while in Neovim
- See `docs/zellij.md` for more details

---

## Troubleshooting

### Plugin not loading

1. Check `:Lazy` for errors
2. Ensure file is in `lua/lazy_plugins/`
3. Restart Neovim

### LSP not working

1. Check if server is installed: `:LspInfo`
2. Install missing server (see LSP section)
3. Check `:LspLog` for errors

### Formatter not working

1. Check if formatter is installed: `which stylua`
2. Install missing formatters: `brew install stylua shfmt ruff`
3. Check `:ConformInfo` for status

### Copilot not suggesting

1. Check status: `:Copilot status`
2. Authenticate: `:Copilot auth`
3. Enable: `:Copilot enable`

# Productivity Tools Overview

This document provides an overview of all productivity tools installed and configured by these dotfiles.

## Terminal Multiplexer: Zellij

Zellij is a modern terminal multiplexer (like tmux) with better defaults.

### Quick Reference

| Key | Action |
|-----|--------|
| `Alt+n` | New tab |
| `Alt+1-9` | Switch to tab |
| `Alt+h/j/k/l` | Navigate panes (also works in locked mode) |
| `Ctrl+p` then `n` | New pane |
| `Ctrl+p` then `x` | Close pane |
| `Ctrl+p` then `f` | Toggle fullscreen |
| `Ctrl+p` then `w` | Toggle floating |

See `profiles/common/files/dotfiles/config/zellij/config.kdl` for full configuration.

---

## Git Tools

### Lazygit

Terminal UI for git. See [lazygit.md](./lazygit.md) for detailed usage.

```bash
lazygit    # Start in current repo
```

### Delta

Syntax-highlighting pager for git diffs. Automatically used by:
- `git diff`
- `git log -p`
- `lazygit` (configured)

### GitHub CLI (gh)

```bash
gh pr create          # Create pull request
gh pr view            # View current PR
gh pr checkout 123    # Checkout PR #123
gh issue list         # List issues
gh repo clone         # Clone a repo
```

### GitHub Copilot CLI

AI-powered command suggestions in your terminal. First-time setup:
```bash
copilot auth          # Authenticate with GitHub
```

**Commands:**
```bash
copilot suggest       # Get shell command suggestions (interactive)
copilot explain       # Explain a command
cps                   # Alias for copilot suggest
cpe                   # Alias for copilot explain
```

**Fish keybinding:** `Ctrl+G Ctrl+S` - Type your intent, press the keybinding to get suggestions

**Examples:**
```bash
cps "find large files over 100MB"
cpe "tar -xvzf archive.tar.gz"
copilot-explain-clipboard   # Explain command from clipboard
```

---

## Neovim (NvChad)

See [neovim-keybindings.md](./neovim-keybindings.md) for complete keybindings.

### Quick Start

| Key | Action |
|-----|--------|
| `<Space>` | Leader key - shows which-key hints |
| `<Space>ff` | Find files |
| `<Space>fg` | Search in files (grep) |
| `s` | Flash jump |
| `<Space>1-5` | Harpoon quick files |
| `<C-n>` | Toggle file tree |

---

## Search & Navigation

### Telescope (in Neovim)

Fuzzy finder for files, text, and more.

| Key | Action |
|-----|--------|
| `<Space>ff` | Find files |
| `<Space>fg` | Live grep |
| `<Space>fr` | Recent files |
| `<Space>fb` | Open buffers |
| `<C-j/k>` | Navigate results |
| `<Enter>` | Open file |
| `<C-x>` | Open in split |
| `<C-v>` | Open in vsplit |

### Ripgrep (rg)

Fast text search from terminal:

```bash
rg "pattern"                    # Search current directory
rg "pattern" src/               # Search in src/
rg -i "pattern"                 # Case insensitive
rg -l "pattern"                 # List files only
rg -C 3 "pattern"               # Show 3 lines context
rg --type py "pattern"          # Only Python files
rg "pattern" -g "*.js"          # Only .js files
rg -v "pattern"                 # Invert match
```

### fd

Fast file finder:

```bash
fd                              # List all files
fd "pattern"                    # Find files matching pattern
fd -e py                        # Find Python files
fd -H                           # Include hidden files
fd -t d                         # Directories only
fd -t f                         # Files only
fd pattern --exec rm {}         # Find and delete
```

---

## Code Formatting & Linting

### Conform (in Neovim)

Auto-formats on save. Configured formatters:
- **Lua**: stylua
- **Python**: ruff
- **JavaScript/TypeScript**: prettier
- **YAML/JSON**: prettier
- **Shell**: shfmt

Manual format: `<Space>cf`

---

## AI Assistants

### GitHub Copilot (in Neovim)

| Key | Action |
|-----|--------|
| `<C-l>` | Accept suggestion |
| `<M-]>` | Next suggestion |
| `<M-[>` | Previous suggestion |
| `<C-]>` | Dismiss |

### Claude Code

AI assistant in the terminal.

```bash
claude                          # Start Claude Code
claude "explain this code"      # Ask a question
```

---

## Development Environment

### Mise (formerly rtx)

Runtime version manager for multiple languages.

```bash
mise install                    # Install versions from .mise.toml
mise use python@3.12            # Use Python 3.12
mise exec -- python script.py   # Run with mise-managed version
mise ls                         # List installed versions
```

### UV

Fast Python package manager.

```bash
uv sync                         # Install dependencies
uv add package                  # Add a package
uv run script.py                # Run with project environment
```

---

## File Management

### NvimTree (in Neovim)

File explorer that opens automatically.

| Key | Action |
|-----|--------|
| `<C-n>` | Toggle tree |
| `<Enter>` | Open file |
| `a` | Create file/directory |
| `d` | Delete |
| `r` | Rename |
| `y` | Copy name |
| `Y` | Copy path |
| `c` | Copy file |
| `p` | Paste |
| `H` | Toggle hidden files |
| `R` | Refresh |

### bat

Better `cat` with syntax highlighting:

```bash
bat file.py                     # View with highlighting
bat --style=numbers file.py     # With line numbers
bat -A file.py                  # Show non-printable chars
```

### eza

Modern `ls`:

```bash
eza                             # List files
eza -la                         # Long format, all files
eza --tree                      # Tree view
eza --git                       # Show git status
eza --icons                     # With icons
```

---

## System Monitoring

### btop

Interactive process viewer:

```bash
btop                            # Start btop
```

| Key | Action |
|-----|--------|
| `h` | Help |
| `q` | Quit |
| `f` | Filter |
| `k` | Kill process |
| `s` | Sort menu |

---

## JSON/YAML Processing

### jq

JSON processor:

```bash
cat file.json | jq '.'                      # Pretty print
cat file.json | jq '.key'                   # Extract key
cat file.json | jq '.[] | .name'            # Extract from array
curl api/data | jq '.results[0]'            # Process API response
```

### yq

YAML processor (same syntax as jq):

```bash
yq '.' file.yml                             # Pretty print
yq '.key' file.yml                          # Extract key
yq -i '.key = "value"' file.yml             # Edit in place
```

---

## Quick Tips

1. **Zellij + Neovim**: Use `<C-h/j/k/l>` to navigate between Neovim splits and Zellij panes seamlessly.

2. **Lazygit + Neovim**: Open lazygit from within Neovim with a custom terminal mapping.

3. **Flash + Operators**: Use `ds` to delete to a flashed location, `ys` to yank to it.

4. **Harpoon workflow**: Add 3-4 files you're actively editing, use `<Space>1-5` to jump instantly.

5. **Telescope + Trouble**: Search TODOs with `<Space>ft`, view them in Trouble with `<Space>xt`.

6. **Git workflow**: Use Gitsigns for quick staging (`<Space>hs`), lazygit for complex operations.

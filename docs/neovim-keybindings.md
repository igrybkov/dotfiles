# Neovim Keybindings Cheatsheet

This document covers all custom keybindings configured in this NvChad setup.
Leader key is `<Space>`.

## Key Notation

| Notation | Key | Example |
|----------|-----|---------|
| `<C-x>` | Control + x | `<C-n>` = Ctrl+n |
| `<S-x>` | Shift + x | `<S-h>` = Shift+h |
| `<A-x>` or `<M-x>` | Alt/Option + x | `<A-j>` = Alt+j |
| `<D-x>` | Command + x (Mac) | `<D-s>` = Cmd+s |
| `<Space>` or `<leader>` | Space bar | `<Space>ff` = Space then f then f |
| `<CR>` | Enter/Return | |
| `<Esc>` | Escape | |
| `<Tab>` | Tab | |

## Quick Reference

| Key | Action |
|-----|--------|
| `<Space>?` | Show all buffer keybindings (which-key) |
| `<Space>ch` | NvChad cheatsheet |
| `<Space>th` | Theme picker |

---

## Navigation

### Flash (Lightning-fast jumps)

| Key | Mode | Action |
|-----|------|--------|
| `s` | n, x, o | Jump to any location (type 2 chars, then label) |
| `S` | n, x, o | Select treesitter node |
| `f/F/t/T` | n, x, o | Enhanced character motions with labels |
| `r` | o | Remote flash (operator pending) |
| `R` | o, x | Treesitter search |

**Example workflow:**
1. Press `s`
2. Type first 2 characters of where you want to go (e.g., `fu` for "function")
3. Press the highlighted label to jump there

### Harpoon (Quick file switching)

| Key | Action |
|-----|--------|
| `<Space>ma` | Add current file to harpoon |
| `<Space>mm` | Open harpoon menu |
| `<Space>1-5` | Jump to harpoon file 1-5 |
| `<Space>mp` | Previous harpoon file |
| `<Space>mn` | Next harpoon file |

**Example workflow:**
1. Open your most-used files and press `<Space>ma` on each
2. Press `<Space>1` through `<Space>5` to instantly switch between them
3. Use `<Space>mm` to reorder or remove files

### Window Navigation

| Key | Action |
|-----|--------|
| `<C-h/j/k/l>` | Navigate windows (or Zellij panes) |
| `<C-Up/Down/Left/Right>` | Resize windows |

### Buffers vs Tabs

NvChad shows **buffers** as tabs at the top (tabufline). These are different from Vim's actual tabs.

**Buffers** (the "tabs" you see in tabufline):

| Key | Action |
|-----|--------|
| `<S-h>` | Previous buffer (Shift+h) |
| `<S-l>` | Next buffer (Shift+l) |
| `<Space>x` | Close current buffer |
| `<Space>fb` | Find buffer (Telescope) |

**Actual Vim Tabs** (separate workspaces, each can have multiple windows):

| Key | Action |
|-----|--------|
| `:tabnew` | New tab |
| `:tabnew file` | New tab with file |
| `gt` | Next tab |
| `gT` | Previous tab |
| `{n}gt` | Go to tab n (e.g., `2gt` for tab 2) |
| `:tabclose` | Close current tab |
| `:tabonly` | Close all other tabs |
| `:tabs` | List all tabs |

**When to use what:**
- **Buffers + Harpoon**: Best for most workflows. Fast switching with `<S-h/l>` and `<Space>1-5`
- **Tabs**: Useful for separate contexts (e.g., one tab for frontend, one for backend)

---

## Editing

### Surround (Add/change/delete pairs)

| Key | Action | Example |
|-----|--------|---------|
| `ys{motion}{char}` | Add surround | `ysiw"` → surround word with `"` |
| `yss{char}` | Surround line | `yss)` → wrap line in `()` |
| `ds{char}` | Delete surround | `ds"` → delete surrounding `"` |
| `cs{old}{new}` | Change surround | `cs"'` → change `"` to `'` |
| `S{char}` | Surround selection (visual) | Select text, `S"` |

**Surround characters:**
- `"`, `'`, `` ` `` - Quotes
- `(`, `)`, `b` - Parentheses
- `{`, `}`, `B` - Braces
- `[`, `]`, `r` - Brackets
- `<`, `>`, `a` - Angle brackets
- `t` - HTML tag (prompts for tag name)

### General Editing

| Key | Action |
|-----|--------|
| `jk` | Exit insert mode |
| `;` | Enter command mode |
| `<Esc>` | Clear search highlights |
| `<C-s>` | Save file |
| `<A-j/k>` | Move line up/down |
| `</>>` (visual) | Indent and stay in visual mode |

---

## Code & LSP

### Formatting

| Key | Action |
|-----|--------|
| `<Space>cf` | Format buffer |
| `<D-M-l>` | Format buffer (GUI) |

### Diagnostics (Trouble)

| Key | Action |
|-----|--------|
| `<Space>xx` | Toggle all diagnostics |
| `<Space>xX` | Toggle buffer diagnostics |
| `<Space>xL` | Toggle location list |
| `<Space>xQ` | Toggle quickfix list |
| `<Space>xt` | Toggle TODO list |
| `[d` / `]d` | Previous/next diagnostic |
| `[q` / `]q` | Previous/next quickfix item |
| `<Space>d` | Show diagnostic float |

### Todo Comments

| Key | Action |
|-----|--------|
| `[t` / `]t` | Previous/next TODO comment |
| `<Space>ft` | Find all TODOs (Telescope) |
| `<Space>xt` | TODO list in Trouble |

---

## Git

### Gitsigns (Hunks)

| Key | Action |
|-----|--------|
| `]c` / `[c` | Next/previous hunk |
| `<Space>hs` | Stage hunk |
| `<Space>hr` | Reset hunk |
| `<Space>hS` | Stage buffer |
| `<Space>hu` | Undo stage hunk |
| `<Space>hR` | Reset buffer |
| `<Space>hp` | Preview hunk |
| `<Space>hb` | Blame line |
| `<Space>tb` | Toggle line blame |
| `<Space>hd` | Diff this |
| `<Space>td` | Toggle deleted |
| `ih` | Select hunk (text object) |

### Diffview

| Key | Action |
|-----|--------|
| `<Space>gd` | Open diff view |
| `<Space>gh` | File history (current) |
| `<Space>gH` | File history (all) |
| `<Space>gc` | Close diff view |

---

## File Navigation

### Telescope

| Key | Action |
|-----|--------|
| `<Space>ff` | Find files |
| `<Space>fg` | Live grep |
| `<Space>fb` | Buffers |
| `<Space>fh` | Help tags |
| `<Space>fr` | Recent files |
| `<Space>fc` | Commands |
| `<Space>fs` | Grep string under cursor |
| `<Space>ft` | Find TODOs |

### NvimTree

| Key | Action |
|-----|--------|
| `<C-n>` | Toggle file tree |

---

## Undo History

| Key | Action |
|-----|--------|
| `<Space>u` | Toggle undotree |

In undotree:
- `j/k` - Navigate history
- `<Enter>` - Go to state
- `p` - Preview diff
- `q` - Close

---

## NvChad Specific

| Key | Action |
|-----|--------|
| `<Space>th` | Theme picker |
| `<Space>ch` | NvChad cheatsheet |

---

## Tips

1. **Which-key**: If you forget a keybinding, just press `<Space>` and wait - which-key will show all available mappings.

2. **Flash + operators**: Use `s` with operators like `d`, `c`, `y`. Example: `ds` starts delete, then flash lets you select the range.

3. **Harpoon workflow**: Keep 3-4 files you're actively editing in harpoon. It's faster than Telescope for frequent switches.

4. **Surround + motion**: Combine with any motion. `ys2w"` surrounds next 2 words with quotes.

5. **TODO comments**: Use standard formats like `TODO:`, `FIXME:`, `HACK:`, `NOTE:` in comments for highlighting and search.

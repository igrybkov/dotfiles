# Neovim Git Integration

This document covers the git integration plugins for Neovim: **gitsigns.nvim** and **diffview.nvim**.

## Plugins Overview

| Plugin | Purpose |
|--------|---------|
| **gitsigns.nvim** | Git status in sign column, inline blame, hunk operations |
| **diffview.nvim** | View all changed files with diff preview in one place |

---

## diffview.nvim - View All Changes

This is the main plugin for viewing all git changes in one place.

### Opening Diff View

| Keybind | Command | Description |
|---------|---------|-------------|
| `<leader>gd` | `:DiffviewOpen` | **Open diff view with ALL changed files** |
| `<leader>gh` | `:DiffviewFileHistory %` | View history of current file |
| `<leader>gH` | `:DiffviewFileHistory` | View history of entire repo |
| `<leader>gc` | `:DiffviewClose` | Close diff view |

### Diff View Layout

When you press `<leader>gd`, you get:

```
┌──────────────────────────────────────────────────────────────┐
│ File Panel (left)    │  Original (left)  │  Changed (right)  │
│                      │                   │                   │
│  Changes:            │  - removed line   │  + added line     │
│   M src/foo.lua      │    context        │    context        │
│   A src/bar.lua      │  - old code       │  + new code       │
│   D src/baz.lua      │                   │                   │
│                      │                   │                   │
└──────────────────────────────────────────────────────────────┘
```

### File Panel Navigation

| Key | Action |
|-----|--------|
| `j` / `k` | Navigate between files |
| `<CR>` or `o` | Open diff for selected file |
| `<Tab>` | Toggle file panel visibility |
| `s` | Stage/unstage file |
| `S` | Stage all files |
| `U` | Unstage all files |
| `X` | Restore/discard changes to file |
| `R` | Refresh file list |
| `q` | Close diff view |

### Advanced Usage

```vim
" Compare against specific branch
:DiffviewOpen main

" Compare specific commit range
:DiffviewOpen HEAD~3..HEAD

" Compare against remote
:DiffviewOpen origin/main

" View only staged changes
:DiffviewOpen --staged

" View changes in specific path
:DiffviewOpen -- path/to/dir
```

---

## gitsigns.nvim - Git Signs & Hunks

Shows git status in the sign column and provides hunk-level operations.

### Sign Column Indicators

| Sign | Meaning |
|------|---------|
| `│` | Added lines |
| `│` | Changed lines |
| `_` | Deleted line below |
| `‾` | Deleted line above |
| `~` | Changed + deleted |
| `┆` | Untracked file |

### Hunk Navigation

| Keybind | Action |
|---------|--------|
| `]c` | Jump to next hunk |
| `[c` | Jump to previous hunk |

### Hunk Operations

| Keybind | Action |
|---------|--------|
| `<leader>hs` | Stage hunk (normal or visual mode) |
| `<leader>hr` | Reset hunk (discard changes) |
| `<leader>hS` | Stage entire buffer |
| `<leader>hR` | Reset entire buffer |
| `<leader>hu` | Undo stage hunk |
| `<leader>hp` | Preview hunk in popup |
| `<leader>hd` | Show diff of current file |
| `<leader>hD` | Show diff against last commit |

### Blame

| Keybind | Action |
|---------|--------|
| `<leader>hb` | Show blame for current line (detailed popup) |
| `<leader>tb` | Toggle inline blame at end of line |

### Toggle Options

| Keybind | Action |
|---------|--------|
| `<leader>tb` | Toggle current line blame |
| `<leader>td` | Toggle showing deleted lines inline |

### Text Objects

| Keybind | Action |
|---------|--------|
| `ih` | Select hunk (use in visual or operator-pending mode) |

Examples:
- `vih` - Visually select the current hunk
- `dih` - Delete the current hunk
- `yih` - Yank the current hunk

---

## Common Workflows

### Review All Changes Before Commit

1. Press `<leader>gd` to open diffview with all changes
2. Use `j`/`k` to navigate files in the panel
3. Press `<CR>` to view diff for each file
4. Use `s` to stage files you want to commit
5. Press `q` to close when done
6. Run `:!git commit` or use your preferred method

### Review a Specific Change

1. Navigate to the line with the change
2. Press `<leader>hp` to preview the hunk
3. Press `<leader>hs` to stage it, or `<leader>hr` to discard it

### View File History

1. Open a file
2. Press `<leader>gh` to see all commits that changed this file
3. Use `j`/`k` to navigate commits
4. Press `<CR>` to see the diff for that commit

### Compare Branches

```vim
:DiffviewOpen feature-branch..main
```

### Find Who Changed a Line

1. Position cursor on the line
2. Press `<leader>hb` for detailed blame popup
3. Or press `<leader>tb` to toggle persistent inline blame

---

## Keybind Summary (Quick Reference)

### Diffview (`<leader>g` prefix)
- `<leader>gd` - Open diff view (all changes)
- `<leader>gh` - File history (current)
- `<leader>gH` - File history (repo)
- `<leader>gc` - Close diff view

### Gitsigns Hunks (`<leader>h` prefix)
- `<leader>hs` - Stage hunk
- `<leader>hr` - Reset hunk
- `<leader>hS` - Stage buffer
- `<leader>hR` - Reset buffer
- `<leader>hu` - Undo stage
- `<leader>hp` - Preview hunk
- `<leader>hb` - Blame line
- `<leader>hd` - Diff this
- `<leader>hD` - Diff this ~

### Gitsigns Toggles (`<leader>t` prefix)
- `<leader>tb` - Toggle line blame
- `<leader>td` - Toggle deleted

### Navigation
- `]c` / `[c` - Next/previous hunk

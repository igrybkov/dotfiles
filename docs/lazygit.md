# Lazygit Cheatsheet

Lazygit is a terminal UI for git commands. This setup includes delta integration for beautiful diffs.

## Starting Lazygit

```bash
lazygit        # In any git repository
lg             # If you have the alias set up
```

## Interface Panels

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Status     │ 2. Files      │ 4. Commits                  │
│               │               │                             │
│ Branch info   │ Staged/       │ Commit history              │
│               │ Unstaged      │                             │
├───────────────┼───────────────┼─────────────────────────────┤
│ 3. Branches   │               │ 5. Stash                    │
│               │               │                             │
│ Local/Remote  │               │ Stashed changes             │
└───────────────┴───────────────┴─────────────────────────────┘
                        │
                        ▼
              6. Main Panel (diff view with delta)
```

## Navigation

| Key | Action |
|-----|--------|
| `Tab` | Switch between panels |
| `j/k` or `↑/↓` | Move up/down |
| `h/l` or `←/→` | Collapse/expand (for directories) |
| `Ctrl+u/d` | Page up/down in diff |
| `q` | Quit (or go back) |
| `Esc` | Cancel / Go back |
| `?` | Show all keybindings |
| `x` | Open menu for current panel |

## Files Panel (2)

| Key | Action |
|-----|--------|
| `Space` | Stage/unstage file |
| `a` | Stage/unstage all |
| `Enter` | Focus file (see individual lines) |
| `d` | Discard changes (careful!) |
| `e` | Edit file in $EDITOR |
| `o` | Open file in default app |
| `i` | Add to .gitignore |
| `S` | Stash options |
| `s` | Stash all changes |
| `c` | Commit staged |
| `C` | Conventional commit (custom) |
| `A` | Amend last commit |

### Staging Individual Lines

When focused on a file (press `Enter`):

| Key | Action |
|-----|--------|
| `Space` | Stage/unstage line |
| `v` | Start line selection |
| `a` | Stage/unstage hunk |
| `Esc` | Back to files |

## Branches Panel (3)

| Key | Action |
|-----|--------|
| `Space` | Checkout branch |
| `n` | New branch |
| `d` | Delete branch |
| `r` | Rebase current branch onto selected |
| `M` | Merge selected into current |
| `f` | Fast-forward if possible |
| `c` | Checkout by name |
| `P` | Push force with lease (custom) |
| `o` | Create pull request |

## Commits Panel (4)

| Key | Action |
|-----|--------|
| `Enter` | View commit files |
| `Space` | Checkout commit |
| `g` | Reset to commit (soft/mixed/hard) |
| `t` | Revert commit |
| `s` | Squash down |
| `f` | Mark as fixup |
| `r` | Reword commit |
| `e` | Edit commit |
| `d` | Drop commit |
| `C` | Cherry-pick copy |
| `V` | Paste cherry-picked commits |
| `Ctrl+j/k` | Move commit down/up |

## Stash Panel (5)

| Key | Action |
|-----|--------|
| `Space` | Apply stash |
| `g` | Pop stash (apply + delete) |
| `d` | Drop stash |
| `n` | New stash |

## Common Workflows

### Conventional Commit (Custom)

1. Stage your changes
2. Press `C` (capital C) in files panel
3. Select commit type (feat, fix, docs, etc.)
4. Enter scope (optional)
5. Enter commit message

### Interactive Rebase

1. Go to Commits panel
2. Navigate to the commit you want to start from
3. Press `e` to start interactive rebase
4. Use `s` (squash), `f` (fixup), `r` (reword), `d` (drop)
5. Continue with `m` or abort with `Ctrl+c`

### Cherry-pick Between Branches

1. Go to the source branch
2. Find the commit to cherry-pick
3. Press `C` to copy
4. Switch to target branch
5. Press `V` to paste

### Resolving Merge Conflicts

1. Conflicting files show in Files panel
2. Press `Enter` on conflicting file
3. Navigate to conflict markers
4. Press `b` to pick both, `←/→` to pick one side
5. Stage resolved file with `Space`

### Undo Last Commit

1. Go to Commits panel
2. Select the last commit
3. Press `g` (reset)
4. Choose "soft" to keep changes staged

## Delta Integration

This config uses `delta` for syntax-highlighted diffs:
- Side-by-side comparison
- Syntax highlighting
- Line numbers
- Git blame integration

The diffs are rendered in the main panel (bottom) when you select files or commits.

## Tips

1. **Quick commit**: Stage files, press `c`, type message, `Enter`

2. **Fix last commit**: Make changes, stage them, press `A` to amend

3. **Undo staging**: Select staged file, press `Space`

4. **View any file**: Press `o` to open in default app, `e` for editor

5. **Search commits**: Press `/` in commits panel

6. **Copy commit SHA**: Press `y` on a commit

7. **Bisect**: Press `b` to start git bisect from commits panel

8. **Submodules**: Access via panel menu `x` → submodules

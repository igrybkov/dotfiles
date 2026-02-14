# dotfiles

Ansible role to manage dotfiles via symlinks.

## Description

This role manages dotfiles by creating symlinks from a source directory to the home directory. It supports:
- Recursive file-level symlinking
- Directory-level symlinking (opt-in via marker file)
- Dead symlink cleanup
- File copying for sensitive files
- Bin script symlinking
- Profile-specific additional dotfiles directories
- Multi-destination skills symlinking (for AI agent skills)
- Multi-destination agents symlinking (for AI agent definitions)

## Requirements

- macOS or Linux

## Tags

- `dotfiles` - All dotfiles operations

## Role Variables

### `dotfiles_dir`

Source directory containing dotfiles to symlink.

**Default**: `{{ playbook_dir }}/files/dotfiles`

**Note**: This is auto-set by the inventory plugin to `{{ profile_dir }}/files/dotfiles` for each profile.

### `dotfiles_copy_dir`

Source directory containing files to copy (not symlink).

**Default**: `{{ playbook_dir }}/files/dotfiles-copy`

**Note**: This is auto-set by the inventory plugin to `{{ profile_dir }}/files/dotfiles-copy` for each profile.

### `bin_dir`

Source directory containing bin scripts to symlink to ~/.local/bin.

**Default**: `{{ playbook_dir }}/files/bin`

### `additional_dotfiles_dirs`

Optional list of additional dotfiles directories beyond the profile's standard `dotfiles_dir`. Use this to add extra dotfiles directories from non-standard locations.

**Default**: `[]`

### `skill_folders`

List of destination directories for skills (e.g., `["~/.claude/skills", "~/.cursor/skills"]`). Skills from all profiles are merged into each configured destination.

**Default**: `[]`

**Note**: `skills_dir` is auto-set by the inventory plugin to `{{ profile_dir }}/files/skills` for each profile.

### `agent_folders`

List of destination directories for agents (e.g., `["~/.claude/agents", "~/.cursor/agents"]`). Agents from all profiles are merged into each configured destination.

**Default**: `[]`

**Note**: `agents_dir` is auto-set by the inventory plugin to `{{ profile_dir }}/files/agents` for each profile.

### `dotfiles_directory_marker`

Marker filename for directory-level symlinks. Directories containing this file will be symlinked as directories instead of recursively symlinking individual files.

**Default**: `.symlink-as-directory`

### `dotfiles_cleanup_depth`

Maximum depth for recursive dead symlink cleanup.

**Default**: `3`

## Directory Structure

```
profiles/common/files/
├── dotfiles/                    # Symlinked to ~/.*
│   ├── bashrc                   # -> ~/.bashrc
│   ├── gitconfig                # -> ~/.gitconfig
│   └── config/                  # Symlinked to ~/.config/*
│       ├── fish/                # Files symlinked individually
│       │   ├── config.fish      # -> ~/.config/fish/config.fish
│       │   └── functions/       # Files symlinked individually
│       └── karabiner/           # Contains .symlink-as-directory
│           └── .symlink-as-directory  # Entire dir -> ~/.config/karabiner/
├── dotfiles-copy/               # Copied to ~/.*
│   └── secrets                  # -> ~/.secrets (copied, not linked)
└── bin/                         # Symlinked to ~/.local/bin/*
    └── watch-logs               # -> ~/.local/bin/watch-logs

profiles/{profile}/files/
├── dotfiles/                    # Profile-specific dotfiles
│   └── config/
│       └── git/                 # Profile-specific git config
├── skills/                       # AI agent skills (shared across agents)
│   └── git-commit/
│       └── SKILL.md
└── agents/                       # AI agent definitions (shared across agents)
    └── productivity-coach.md
```

## Directory-Level Symlinks

By default, the role symlinks individual files recursively. To symlink an entire directory instead (useful for apps that create files in config directories), add a `.symlink-as-directory` marker file:

```bash
# Create marker to symlink entire directory
touch profiles/common/files/dotfiles/config/karabiner/.symlink-as-directory
```

The role will then create:
```
~/.config/karabiner -> /path/to/dotfiles/profiles/common/files/dotfiles/config/karabiner
```

Instead of symlinking individual files within the directory.

## Dependencies

None

## Example Usage

```yaml
# In profiles/common/config.yml
# Note: dotfiles_dir and dotfiles_copy_dir are auto-set by the inventory plugin
# Only override if you need a non-standard location

# Optional: Add extra dotfiles directories beyond the standard location
additional_dotfiles_dirs:
  - "{{ playbook_dir }}/files/extra-dotfiles"

# Configure skills and agents to be symlinked to multiple agent destinations
skill_folders:
  - ~/.claude/skills
  - ~/.cursor/skills

agent_folders:
  - ~/.claude/agents
  - ~/.cursor/agents
```

## Behavior

1. **Ensure ~/.config exists**: Creates directory if missing
2. **Dead symlink cleanup**: Removes broken symlinks pointing to the dotfiles repo in:
   - `~/` (depth 1, dotfiles only)
   - `~/.config` (configurable depth)
   - `~/.local/bin` (depth 1)
   - Skill folders (from aggregated `skill_folders`)
   - Agent folders (from aggregated `agent_folders`)
3. **Home directory symlinking**: Files in `dotfiles_dir` → `~/.{filename}` (excluding `config/`)
4. **Config symlinking**: Files in `dotfiles_dir/config/` → `~/.config/{filename}`
5. **File copying**: Files in `dotfiles_copy_dir` → `~/.{filename}` (mode 0600)
6. **Bin scripts**: Files in `bin_dir` → `~/.local/bin/{filename}`
7. **Skills symlinking**: Files in `skills_dir` → each destination in aggregated `skill_folders`
8. **Agents symlinking**: Files in `agents_dir` → each destination in aggregated `agent_folders`
9. **Additional dotfiles**: Process `additional_dotfiles_dirs` from profiles

## Conflict Detection

The role fails with a clear error message if:
- A symlink target exists as a regular file (not a symlink)
- A directory symlink target exists as a non-symlink directory

This prevents accidental overwrites. Remove or backup conflicting files manually.

## Notes

- Files in `config/` subdirectory get special handling (symlinked to `~/.config/`)
- Copied files use mode `0600` for security
- Dead symlink cleanup only targets symlinks pointing to the dotfiles repo (fast)
- Empty directories left behind after dead symlink cleanup are removed (except in `~/` root)
- Uses `force: false` - never overwrites existing files or directories

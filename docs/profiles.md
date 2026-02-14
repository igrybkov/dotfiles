# Profiles System

Profiles provide a way to manage different machine configurations (work vs personal) with profile-specific packages, dotfiles, SSH configs, and git settings.

## Nested Profile Support

Profiles support up to three levels of directory nesting:

**Level 1:** `profiles/{profile}/config.yml`
- Profile name matches directory name (e.g., `work`, `personal`, `common`)
- Example: `profiles/work/` -> profile name `work`

**Level 2:** `profiles/{repo}/{profile}/config.yml`
- Profile name is dash-separated from path (e.g., `myrepo-work`, `myrepo-personal`)
- Useful for organizing multiple company-specific profiles in a single git repo
- Example: `profiles/mycompany/work/` -> profile name `mycompany-work`

**Level 3:** `profiles/{dir}/{repo}/{profile}/config.yml`
- Profile name uses full dash-separated path
- Useful for git-ignoring a parent directory (e.g., `private/`) and cloning repos into it
- Example: `profiles/private/personal/productivity/` -> profile name `private-personal-productivity`

**Important:** A directory is only considered a profile if it contains a `config.yml` file.

## Directory Structure

```
profiles/
├── .gitignore              # Ignores private profiles, allows work/ and personal/
├── common/                 # Level 1 profile
│   └── config.yml          # Profile name: "common"
├── work/                   # Level 1 profile
│   └── config.yml          # Profile name: "work"
├── {company}/              # Git repo containing Level 2 profiles
│   ├── .git/               # Git repo at repo level (not profile level)
│   ├── work/               # Level 2 profile
│   │   └── config.yml      # Profile name: "company-work"
│   └── personal/           # Level 2 profile
│       └── config.yml      # Profile name: "company-personal"
├── private/                # Git-ignored directory for cloning repos
│   └── {repo}/             # Git repo cloned into private/
│       ├── .git/           # Git repo at level 2 (private/{repo}/.git)
│       └── {profile}/      # Level 3 profile
│           └── config.yml  # Profile name: "private-repo-profile"
└── {private-profile}/      # Git-ignored private profiles (level 1)
    ├── config.yml          # Profile configuration (REQUIRED)
    ├── files/dotfiles/     # Profile dotfiles (symlinked to ~/.*)
    ├── packages/           # Python packages (installed via pipx)
    ├── tasks/main.yml      # Custom Ansible tasks (optional)
    ├── roles/              # Custom Ansible roles (optional)
    ├── requirements.yml    # Custom Ansible Galaxy dependencies (optional)
    └── secrets.yml         # Profile-specific encrypted secrets (optional)

profiles/common/files/
├── bin/                    # Custom scripts (symlinked to ~/.local/bin/)
├── claude/                 # Claude Code commands, agents, skills source
├── dotfiles/               # Common dotfiles (symlinked for all profiles)
│   └── config/             # XDG config files (symlinked to ~/.config/)
├── dotfiles-copy/          # Files copied (not symlinked) to home
└── fonts/                  # Fonts -> copied to ~/Library/Fonts

profiles/work/files/
├── dotfiles/               # Work-specific dotfiles
│   └── config/git/         # Work git configs (company.gitconfig, etc.)
└── dotfiles-copy/          # Work files copied to home (if needed)
```

## How Profiles Work

1. **Dynamic Inventory Plugin** (`ansible_plugins/inventory/dotfiles_profiles.py`): Scans `profiles/` directory at depth 1, 2, and 3 for directories containing `config.yml`
2. **Profile Discovery Package** (`packages/dotfiles_profile_discovery/`): Shared logic used by both CLI and Ansible inventory plugin for consistent profile discovery
3. **Profile Config** (`profiles/{path}/config.yml`): Defines profile-specific variables; required for a directory to be recognized as a profile
4. **Profile Naming**: Path is converted to name using dash-separator (e.g., `work` -> `work`, `myrepo/work` -> `myrepo-work`, `private/myrepo/work` -> `private-myrepo-work`)
5. **Profile Dotfiles** (`profiles/{path}/files/dotfiles/`): Profile-specific dotfiles symlinked to home directory
6. **Git Config Injection**: The `gitconfig` role injects profile-specific git config into `~/.config/git/local.gitconfig`

## Profile Configuration (config.yml)

Each profile's `config.yml` can define:

```yaml
---
# Profile configuration for dynamic inventory
profile:
  name: work              # Profile name (default: directory name)
  host: work-profile      # Ansible host name (default: {name}-profile)
  priority: 200           # Execution order (default: 1000, lower = earlier)

# Auto-discovered variables (set automatically by inventory plugin):
#   profile_name: Name of the profile (from profile.name or directory name)
#   profile_dir: Path to profile directory
#   dotfiles_dir: {{ profile_dir }}/files/dotfiles
#   dotfiles_copy_dir: {{ profile_dir }}/files/dotfiles-copy
#   bin_dir: {{ profile_dir }}/files/bin
#   packages_dir: {{ profile_dir }}/packages
#   profile_tasks_file: {{ profile_dir }}/tasks/main.yml
#   profile_roles_dir: {{ profile_dir }}/roles
#   profile_requirements_file: {{ profile_dir }}/requirements.yml

# Package lists (merged with common packages)
brew_packages:
  - name: some-package
  - name: unwanted-package
    state: absent          # Remove a package for this profile

cask_packages:
  - name: some-app

mas_packages:
  - name: App Name
    id: 123456789

# SSH client configuration
ssh_client_config:
  - host: "*.example.com"
    hostname: example.com
    remote_user: myuser
    identity_file: ~/.ssh/example.pub

# YAML config settings (merged into existing files)
yaml_configs:
  - file: ~/.config/hive/hive.yml
    content:
      agents:
        order:
          - claude
          - cursor
          - copilot
```

## Creating a New Profile

### Using the CLI (recommended)

```bash
# List all available profiles with their status
./dotfiles profile list

# Create level 1 profile with git repo
./dotfiles profile bootstrap mycompany

# Create level 2 profile (git at repo level)
./dotfiles profile bootstrap mycompany/work
./dotfiles profile bootstrap mycompany/personal

# Create level 3 profile (for repos cloned into git-ignored directory)
./dotfiles profile bootstrap private/personal/productivity

# Create without git initialization
./dotfiles profile bootstrap mycompany --no-git
./dotfiles profile bootstrap mycompany/work --no-git
./dotfiles profile bootstrap private/personal/work --no-git
```

For nested profiles:
- Level 2: First profile (`mycompany/work`) initializes git at `profiles/mycompany/`
- Level 3: First profile (`private/myrepo/work`) initializes git at `profiles/private/myrepo/`
- Subsequent profiles in the same repo are added to the existing git repo
- Profile names are dash-separated: `mycompany-work`, `private-myrepo-work`

This creates a complete profile structure with:
- `config.yml` with commented examples
- `files/dotfiles/config/` directory
- `files/gitconfig/` directory for git config fragments and gitignore
- `packages/` directory for local Python packages (installed via pipx)
- `tasks/main.yml` for custom Ansible tasks
- `roles/` directory for custom roles
- `requirements.yml` for custom Ansible Galaxy dependencies (optional, add as needed)
- `.gitignore` for vault password file

### Manual creation

1. **Create profile directory:**
   ```bash
   mkdir -p profiles/{profile-name}
   ```

2. **Create config.yml:**
   ```yaml
   ---
   profile:
     name: {profile-name}
     # host: {profile-name}-profile  # Ansible host name (default: {name}-profile)
     # priority: 1000                 # Execution order (lower = earlier)

   # Add profile-specific configuration...
   brew_packages: []
   cask_packages: []
   ```

3. **Add profile-specific dotfiles (optional):**
   ```bash
   mkdir -p profiles/{profile-name}/files/dotfiles/config/git
   # Add profile-specific config files
   ```

4. **For private profiles**, they're automatically git-ignored. For public profiles, update `profiles/.gitignore` to include them.

### Migrating existing profiles

If you have profiles using the old `host:` structure, migrate them using:
```bash
./dotfiles profile migrate --all           # Migrate all profiles
./dotfiles profile migrate common personal # Migrate specific profiles
./dotfiles profile migrate --all --dry-run # Preview changes
```

## Built-in vs Private Profiles

- **Built-in profiles** (`work`, `personal`): Committed to repo, defined in `profiles/.gitignore` allowlist
- **Private profiles**: Any other directory in `profiles/` is git-ignored and can contain sensitive work-specific configuration

## Profile Priority

Profiles are processed in priority order (lower number = processed first):
- `default`: 100
- `common`: 150
- `work`, `personal`: 200
- All others: 1000

## Profile Git Repositories

**IMPORTANT:** Private profiles can have their own git repositories. Changes in these profile directories are **not tracked by the main dotfiles repo** and must be committed separately.

**Git repository placement:**
- **Level 1 profiles:** Git repo at `profiles/{profile}/.git`
- **Level 2 profiles:** Git repo at `profiles/{repo}/.git` (containing multiple profiles)
- **Level 3 profiles:** Git repo at `profiles/{dir}/{repo}/.git` (e.g., `profiles/private/myrepo/.git`)

The CLI automatically detects git repositories at levels 1 and 2 within `profiles/`.

When working with code in `profiles/`, check for `.git` at the appropriate level:
- Level 1: `profiles/{profile}/.git`
- Level 2: `profiles/{repo}/.git`
- Level 3: `profiles/{dir}/{repo}/.git`

### Setting up a level 1 profile as a separate repo

```bash
# After creating a profile
cd profiles/mycompany
git remote add origin git@github.com:you/dotfiles-mycompany.git
git push -u origin main
```

### Setting up level 2 profiles as a shared repo

```bash
# Create first profile (initializes git at repo level)
./dotfiles profile bootstrap mycompany/work

# Add more profiles to the same repo
./dotfiles profile bootstrap mycompany/personal

# Add remote (at repo level, not profile level)
cd profiles/mycompany
git remote add origin git@github.com:you/dotfiles-mycompany.git
git push -u origin main
```

### Setting up level 3 profiles (repos in git-ignored directory)

```bash
# First, ensure the parent directory is git-ignored
# profiles/.gitignore should contain: private/

# Clone or create a repo in the private directory
cd profiles/private
git clone git@github.com:you/personal-profiles.git

# Or create from scratch
./dotfiles profile bootstrap private/personal/productivity
cd profiles/private/personal
git remote add origin git@github.com:you/personal-profiles.git
git push -u origin main
```

### CLI integration with profile repos

The `pull`, `push`, and `sync` commands automatically handle profile repos:
- Discovers all profile directories that contain a `.git` folder
- Performs git operations on each profile repo in addition to the main repo
- Shows clear output indicating which repo is being synced

### Checking for uncommitted changes

```bash
# Check main repo
git status

# Check specific profile repo
git -C profiles/mycompany status

# The CLI will warn about uncommitted changes during install
./dotfiles install --all
```

## Custom Tasks, Roles, and Galaxy Requirements

Profiles can include custom Ansible tasks that run after all standard roles:

### Custom Tasks (`profiles/{name}/tasks/main.yml`)

```yaml
---
# Available variables (auto-discovered by inventory plugin):
#   profile_name: Name of the profile
#   profile_dir: Path to profile directory
#   profile_roles_dir: Path to roles/ in this profile
#   profile_requirements_file: Path to requirements.yml in this profile
#   dotfiles_dir: Path to files/dotfiles/ in this profile
#   dotfiles_copy_dir: Path to files/dotfiles-copy/ in this profile
#   bin_dir: Path to files/bin/ in this profile
#   packages_dir: Path to packages/ in this profile

- name: Install custom package
  community.general.homebrew:
    name: my-internal-tool
    state: present

- name: Include profile-specific role
  ansible.builtin.include_role:
    name: "{{ profile_roles_dir }}/my_custom_role"
```

### Custom Roles (`profiles/{name}/roles/{role_name}/`)

```
profiles/mycompany/roles/
└── internal_tools/
    ├── tasks/main.yml
    └── defaults/main.yml
```

### Custom Galaxy Requirements (`profiles/{name}/requirements.yml`)

Profiles can define their own Ansible Galaxy dependencies. These are installed in addition to the main `requirements.yml`:

```yaml
# profiles/mycompany/requirements.yml
---
collections:
  - name: company.internal_collection
    source: https://galaxy.internal.company.com
    version: "1.0.0"

roles:
  - name: company.setup_role
    src: https://github.com/company/setup-role
```

Profile requirements are installed:
- During `./dotfiles install` (before playbook execution)
- During `./dotfiles upgrade` or `./dotfiles sync` (with `--force` to upgrade)

## Git Configuration Integration

The `gitconfig` role manages profile-specific git configuration using a conf.d fragment pattern. Each profile provides `*.gitconfig` files in `files/gitconfig/` which are symlinked to `~/.config/git/conf.d/` with priority-prefixed names.

### Adding git config to a profile

Create `profiles/work/files/gitconfig/gitconfig.gitconfig`:

```gitconfig
[user]
    email = work@company.com

[includeIf "hasconfig:remote.*.url:git@github.com:company/**"]
    path = ~/.config/git/company.gitconfig
```

### Adding gitignore patterns

Create `profiles/work/files/gitconfig/gitignore`:

```gitignore
# Work-specific ignores
.internal-tools/
```

The global `~/.gitconfig` includes `~/.config/git/conf.d/includes.gitconfig`, which is generated by the role. See `roles/gitconfig/README.md` for full documentation.

## Profile-Local Python Packages

Profiles can include Python packages that are installed via pipx in editable mode. This allows writing complex CLI tools in Python with proper testing support.

### Directory Structure

```
profiles/{profile}/packages/
└── {package-name}/
    ├── pyproject.toml
    ├── src/{package_name}/
    │   ├── __init__.py
    │   └── cli.py
    └── tests/
```

### Configuration

```yaml
# profiles/{profile}/config.yml
pipx_packages:
  # PyPI package (existing syntax)
  - name: some-pypi-package

  # Local package (installed in editable mode)
  # Paths starting with "packages/" are relative to profile_dir
  - name: my-tool
    path: packages/my-tool
    editable: true  # default for local packages
```

### Sample `pyproject.toml`

```toml
[build-system]
build-backend = "hatchling.build"
requires = ["hatchling"]

[project]
name = "my-tool"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["click>=8.0", "rich>=13.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff>=0.1"]

[project.scripts]
my-tool = "my_tool.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/my_tool"]
```

### Development Workflow

```bash
# Test package locally
cd profiles/myprofile/packages/my-tool
uv venv && uv pip install -e ".[dev]"
uv run pytest

# Install via dotfiles (editable mode - changes take effect immediately)
./dotfiles install pipx
```

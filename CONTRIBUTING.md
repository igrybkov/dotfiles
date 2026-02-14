# Contributing

Thanks for your interest in contributing! This guide will help you get started.

## Getting Started

1. **Fork and clone** the repository:

   ```bash
   git clone https://github.com/<your-username>/dotfiles.git ~/.dotfiles
   cd ~/.dotfiles
   ```

2. **Install dependencies** (requires [mise](https://mise.jdx.dev/)):

   ```bash
   mise x -- uv sync --managed-python --frozen
   ```

3. **Install pre-commit hooks:**

   ```bash
   mise x -- uv run pre-commit install
   ```

4. **Run the linters** to make sure everything is clean:

   ```bash
   mise x -- uv run pre-commit run --all-files
   ```

## Creating Custom Profiles

Profiles let you organize configuration for different machines or environments. See [docs/profiles.md](docs/profiles.md) for full documentation.

```bash
# Create a new profile with standard structure
dotfiles bootstrap-profile mycompany

# Create without git initialization
dotfiles bootstrap-profile mycompany --no-git

# Create nested profiles (shared git repo)
dotfiles bootstrap-profile mycompany/work
dotfiles bootstrap-profile mycompany/personal
```

This generates a complete profile directory with `config.yml`, dotfile directories, custom tasks, and roles scaffolding.

## Adding Packages

Edit `profiles/common/config.yml` (shared across all machines) or `profiles/{profile}/config.yml` (profile-specific):

```yaml
# Homebrew formulae
brew_packages:
  - name: ripgrep
  - name: fd

# Homebrew casks
cask_packages:
  - name: visual-studio-code
  - name: firefox

# Homebrew taps
brew_taps:
  - name: homebrew/cask-fonts

# Mac App Store apps (requires mas CLI)
mas_packages:
  - name: Magnet
    id: 441258766
```

Then run the relevant install command:

```bash
dotfiles install brew        # Formulae
dotfiles install cask        # Casks
dotfiles install mas         # Mac App Store apps
```

## Adding Dotfiles

Place files in the appropriate profile's directory:

| Source location | Destination | Method |
|----------------|-------------|--------|
| `profiles/{profile}/files/dotfiles/{file}` | `~/.{file}` | Symlink |
| `profiles/{profile}/files/dotfiles/config/{dir}` | `~/.config/{dir}` | Symlink |
| `profiles/{profile}/files/dotfiles-copy/{file}` | `~/{file}` | Copy |
| `profiles/{profile}/files/bin/{script}` | `~/.local/bin/{script}` | Symlink |

Then run:

```bash
dotfiles install dotfiles
```

## Adding Roles

1. **Create the role directory:**

   ```bash
   mkdir -p roles/{role_name}/tasks
   ```

2. **Create `roles/{role_name}/tasks/main.yml`:**

   ```yaml
   ---
   - name: Do something
     ansible.builtin.debug:
       msg: "Hello from {{ role_name }}"
   ```

3. **Optionally add defaults** in `roles/{role_name}/defaults/main.yml`.

4. **Add the role** to the appropriate play in `playbook.yml`.

5. **Tag naming convention:**
   - Role directory names use **underscores**: `gh_repos`, `mcp_servers`
   - Ansible tags use **kebab-case**: `gh-repos`, `mcp-servers`

6. **Document the role** in `roles/{role_name}/README.md`.

## Submitting PRs

### Branch naming

Use descriptive branch names:

```
feat/add-neovim-role
fix/brew-cask-install
docs/update-profile-guide
```

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): subject

# Examples:
feat(role): add neovim configuration role
fix(brew): handle missing cask gracefully
docs(profiles): clarify nested profile setup
refactor(playbook): extract common tasks into shared file
chore(deps): update dependency community.docker to v5
```

### What to include in a PR

- A clear description of what changed and why
- Any new roles should include a `README.md`
- Tests passing (`pytest` + `pre-commit`)
- No personal data (API keys, emails, hostnames)

## Running Tests

```bash
# Run unit tests
mise x -- uv run pytest -v

# Run all pre-commit hooks (linting + formatting)
mise x -- uv run pre-commit run --all-files

# Run a specific linter
mise x -- uv run yamllint .
mise x -- uv run ansible-lint
mise x -- uv run ruff check .
```

## Code Style

Code style is enforced automatically via pre-commit hooks:

| Tool | Scope |
|------|-------|
| [yamllint](https://github.com/adrienverge/yamllint) | YAML files |
| [ansible-lint](https://ansible.readthedocs.io/projects/lint/) | Ansible playbooks and roles |
| [ruff](https://docs.astral.sh/ruff/) | Python code |
| [shellcheck](https://www.shellcheck.net/) | Shell scripts |

Run `mise x -- uv run pre-commit run --all-files` before submitting to catch any issues early.

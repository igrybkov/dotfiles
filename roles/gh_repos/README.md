# gh_repos

Ansible role to clone and manage GitHub repositories using the `gh` CLI.

## Features

- Installs `gh` CLI via Homebrew if not present
- Clones repositories using `gh repo clone`
- Supports `present` and `latest` states for controlling update behavior
- Supports custom destination paths
- Supports checking out specific branches or tags

## Requirements

- macOS with Homebrew
- GitHub CLI authentication (`gh auth login`)

## Role Variables

### `gh_repos`

List of repositories to clone. Each item can be:

- **String**: `"owner/repo"` - clones to default destination
- **Dict**: with the following options:

| Option   | Required | Default                        | Description                                      |
|----------|----------|--------------------------------|--------------------------------------------------|
| `repo`   | Yes      | -                              | Repository in `owner/repo` format                |
| `dest`   | No       | `~/Projects/{repo_name}`       | Destination path                                 |
| `state`  | No       | `present`                      | `present` or `latest`                            |
| `branch` | No       | -                              | Branch to checkout                               |
| `tag`    | No       | -                              | Tag to checkout (takes precedence over `branch`) |

### `gh_repos_default_dest`

Default destination directory for repos. Repository name will be appended.

**Default**: `~/Projects`

## States

- **`present`** (default): Only clone if the repository doesn't exist. Does not update existing repos.
- **`latest`**: Fetch and pull changes on every run. For tags, fetches all tags and checks out the specified tag.

## Example Usage

```yaml
gh_repos:
  # Simple format - clones to ~/Projects/repo-name
  - owner/simple-repo

  # Full format with custom destination and auto-update
  - repo: owner/another-repo
    dest: ~/Code/custom-path
    state: latest

  # Pin to a specific tag
  - repo: owner/versioned-repo
    tag: v1.0.0

  # Use a specific branch
  - repo: owner/feature-repo
    branch: develop

  # Combine options
  - repo: owner/project
    dest: ~/Work/project
    state: latest
    branch: main
```

## Running

```bash
# Run only gh_repos role
./dotfiles install gh_repos

# Run with other tags
./dotfiles install --all
```

## Dependencies

None. The role will install `gh` CLI via Homebrew if not already installed.

## Notes

- The `gh` CLI must be authenticated before running this role (`gh auth login`)
- When using `state: latest` with a `tag`, the role fetches all tags and checks out the specified tag
- When using `state: latest` with a `branch`, the role performs `git pull --ff-only`
- The role uses `gh repo clone` which handles SSH/HTTPS configuration automatically based on your `gh` settings

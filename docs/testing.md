# Testing

The repository uses pytest for unit tests and Molecule for integration tests.

## Running Tests

```bash
# Unit tests (CLI, packages)
mise x -- uv run pytest -v

# List Molecule scenarios
mise x -- molecule list

# Run project-level integration tests
mise x -- molecule test -s default

# Run individual role tests
cd roles/dotfiles && mise x -- molecule test
cd roles/ssh_config && mise x -- molecule test
cd roles/pip && mise x -- molecule test

# Run macOS integration tests (requires Tart: brew install cirruslabs/cli/tart)
mise x -- molecule test -s macos-integration
```

## Test Structure

- **`packages/*/tests/`**: Unit tests for CLI and packages (pytest)
- **`molecule/default/`**: Docker-based integration tests for cross-platform roles
- **`molecule/macos-integration/`**: Tart VM-based tests for macOS-specific roles
- **`roles/*/molecule/default/`**: Individual role integration tests

## CI Pipeline

The CI pipeline (`.github/workflows/ci.yml`) runs:
- `python-tests`: pytest unit tests on every PR
- `molecule-docker`: Role integration tests in Docker (dotfiles, ssh_config, pip)
- `molecule-default`: Project-level integration scenario
- `molecule-macos`: macOS integration (manual trigger via workflow_dispatch)

# CLI Package Structure

The Python CLI is organized as a proper package in `packages/dotfiles_cli/`:

```
packages/dotfiles_cli/
├── pyproject.toml              # Package configuration with Click dependency
├── src/dotfiles_cli/
│   ├── __init__.py             # Package version
│   ├── app.py                  # Main CLI app and entry point
│   ├── constants.py            # Shared constants (DOTFILES_DIR, NON_SUDO_TAGS)
│   ├── types.py                # Type definitions and dataclasses
│   ├── utils.py                # Utility functions
│   ├── commands/               # CLI command implementations
│   │   ├── completion.py       # Shell completion commands
│   │   ├── config.py           # Config command
│   │   ├── edit.py             # Edit command
│   │   ├── git.py              # Pull/push/sync commands
│   │   ├── install.py          # Install command
│   │   ├── profile.py          # profile command group (list, bootstrap)
│   │   ├── secrets.py          # Secret management commands
│   │   └── upgrade.py          # Upgrade command
│   ├── profiles/               # Profile discovery and configuration
│   │   ├── config.py           # Profile config loading
│   │   ├── discovery.py        # Profile directory discovery
│   │   ├── git.py              # Profile git repo operations
│   │   └── selection.py        # Profile selection logic
│   └── vault/                  # Ansible Vault operations
│       ├── operations.py       # Vault read/write operations
│       └── password.py         # Vault password management
└── tests/                      # Unit tests
```

The package uses UV workspace configuration. The root `pyproject.toml` includes it as a workspace member, allowing `uv sync` to install it in development mode.

# MCP Servers Role

Manages [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server configurations for Claude Code and Claude Desktop.

## Features

- **Declarative configuration**: Define MCP servers as a list with `name` field as unique identifier
- **Multiple transport types**: Supports both command-based (stdio) and URL-based (HTTP/SSE) servers
- **Multiple config files**: Updates both Claude Code (`~/.mcp.json`) and Claude Desktop configs
- **Git repository support**: Automatically clone and update git-based MCP servers
- **Secret management**: Supports both Ansible Vault and 1Password CLI for secure secret storage
- **Non-destructive**: Preserves existing unmanaged servers in config files
- **Secure file permissions**: Configs with secrets get `0600` permissions automatically

## Requirements

- Python 3.x
- Git (for git-based servers)
- 1Password CLI (`op`) - optional, only if using `op://` references

## Role Variables

### `mcp_servers`

List of MCP servers to manage. Each server must have a `name` field and either `command` (for stdio transport) or `url` (for HTTP/SSE transport).

#### Command-based Servers (stdio transport)

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Unique identifier for the server |
| `command` | Yes | The command to run the server |
| `args` | No | List of arguments to pass to the command |
| `env` | No | Environment variables resolved at install time (supports vault and 1Password secrets; values end up plaintext in the config file) |
| `secret_env` | No | Environment variables resolved at **spawn time** by `bin/run-with-secrets.sh` — values are vault key paths, never the secrets themselves. See "Runtime-resolved secrets" below. |
| `description` | No | Short human-readable description. Surfaced by mcp-hub in `list_servers`/`search`. |
| `tags` | No | List of tags for grouping/filtering. Surfaced by mcp-hub in `list_servers`/`search`. |
| `state` | No | `present` (default) or `absent` |
| `config_files` | No | List of config files to update (overrides defaults) |
| `git_repo` | No | Git repository URL to clone |
| `git_dest` | No | Destination path for git clone |
| `git_version` | No | Git ref to checkout (default: HEAD) |
| `git_force` | No | Force git checkout to specified version (default: false). Requires `git_force_reset` if local changes exist |
| `git_force_reset` | No | Allow destructive operations even with uncommitted/unpushed changes (default: false) |
| `post_clone` | No | Command(s) to run after cloning. Can be a string (e.g., `uv sync`) or a list of commands (e.g., `["uv sync", "npm install"]`) |

#### URL-based Servers (HTTP/SSE transport)

| Property | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Unique identifier for the server |
| `url` | Yes | The HTTP endpoint URL for the MCP server |
| `transport` | No | Transport type (e.g., `sse`, `streamable-http`) |
| `headers` | No | HTTP headers (supports vault and 1Password secrets) |
| `description` | No | Short human-readable description. Surfaced by mcp-hub in `list_servers`/`search`. |
| `tags` | No | List of tags for grouping/filtering. Surfaced by mcp-hub in `list_servers`/`search`. |
| `state` | No | `present` (default) or `absent` |
| `config_files` | No | List of config files to update (overrides defaults) |

### `mcp_default_config_files`

List of config files to update when `config_files` is not specified per server.

Default:
```yaml
mcp_default_config_files:
  - ~/.mcp.json  # Claude Code
  - ~/Library/Application Support/Claude/claude_desktop_config.json  # Claude Desktop
```

**Note:** All paths support `~/` for home directory expansion (expanded by the role).

### `mcp_servers_git_base`

Base directory for git-cloned MCP servers when `git_dest` is not specified.

Default: `~/.local/share/mcp-servers`

## Secret Management

### Runtime-resolved secrets via `secret_env` (preferred for stdio servers)

Use `secret_env` to resolve secrets at **server spawn time** via `bin/run-with-secrets.sh`. The rendered MCP config contains only vault key paths — never the secret values themselves — so config files are safe to share, back up, or commit.

```yaml
mcp_servers:
  - name: habitify-mcp-server
    command: npx
    args: ["-y", "@sargonpiraev/habitify-mcp-server"]
    env:
      LOG_LEVEL: debug            # plain env still works for non-secrets
    secret_env:
      HABITIFY_API_KEY: mcp_secrets.habitify.api_key
```

The role rewrites this into:

```json
{
  "habitify-mcp-server": {
    "command": "<dotfiles>/bin/run-with-secrets.sh",
    "args": [
      "-p", "<profile>",
      "HABITIFY_API_KEY=mcp_secrets.habitify.api_key",
      "--",
      "npx", "-y", "@sargonpiraev/habitify-mcp-server"
    ],
    "env": {"LOG_LEVEL": "debug"}
  }
}
```

The wrapper does a single batched `dotfiles secret get -p <profile> -0 <keys...>` call (one vault decrypt regardless of N secrets). It aborts with a loud error before `exec` if any key fails to resolve, so misconfigurations fail fast instead of silently running with empty env vars.

Limitations:
- stdio servers only (URL-based `headers:` still need install-time resolution — see below)
- requires the repo's `.vault_password` to be readable when a server spawns (no interactive prompt during MCP-host launches)

### Install-time secrets via `vault_secret` lookup

Use the `vault_secret` Jinja lookup for fields that can't be rewritten at runtime (notably `headers:` on URL-based servers). These values are resolved at playbook time and written plaintext into the config file, which then gets `0600` mode.

Store secrets in your profile's `secrets.yml` (encrypted with Ansible Vault):

```yaml
# profiles/<profile>/secrets.yml (encrypted)
mcp_secrets:
  habitify:
    api_key: "your-api-key-here"
  readwise:
    access_token: "your-token-here"
```

Reference them via:

```yaml
mcp_servers:
  - name: authenticated-api
    url: "https://secure.example.com/mcp"
    transport: streamable-http
    headers:
      x-api-key: "{{ lookup('vault_secret', 'mcp_secrets.secure.api_key') }}"
```

`vault_secret` still works on `env:` for backward compat, but prefer `secret_env:` for new stdio servers.

### CLI Commands

The dotfiles CLI provides commands for managing vault secrets:

```bash
# Set a secret
./dotfiles secret set mcp_secrets.myserver.api_key

# Get a secret
./dotfiles secret get mcp_secrets.myserver.api_key

# List all secrets
./dotfiles secret list

# Edit secrets file directly
./dotfiles secret edit
```

### 1Password CLI

For 1Password integration, use `op://` references:

```yaml
mcp_servers:
  - name: my-server
    command: my-server
    env:
      API_KEY: "op://Private/my-server/api-key"
```

The role will automatically resolve these references using the 1Password CLI.

## Example Configuration

### Command-based Servers (stdio transport)

```yaml
# profiles/common/config.yml
mcp_servers:
  # UV tool run from git (no local install required)
  - name: omnifocus
    command: uv
    args: ["tool", "run", "--from", "git+https://github.com/igrybkov/omnifocus-mcp", "omnifocus-mcp"]

  # NPX server with secret
  - name: habitify-mcp-server
    command: npx
    args: ["-y", "@sargonpiraev/habitify-mcp-server"]
    env:
      HABITIFY_API_KEY: "{{ lookup('vault_secret', 'mcp_secrets.habitify.api_key') }}"

  # Git-based server with UV
  - name: things
    git_repo: https://github.com/hald/things-mcp
    git_dest: ~/Projects/mcp-servers/things-mcp
    command: uv
    args:
      - "--directory"
      - ~/Projects/mcp-servers/things-mcp
      - "run"
      - "things_server.py"

  # Git-based server with post-clone setup (single command)
  - name: ynab-mcp-server
    git_repo: https://github.com/klauern/mcp-ynab
    git_dest: ~/Projects/mcp-servers/mcp-ynab
    post_clone: "uv sync"
    command: ~/Projects/mcp-servers/mcp-ynab/.venv/bin/mcp-ynab

  # Git-based server with multiple post-clone commands
  - name: complex-server
    git_repo: https://github.com/user/complex-server
    git_dest: ~/Projects/mcp-servers/complex-server
    post_clone:
      - "uv sync"
      - "npm install"
      - "make build"
    command: ~/Projects/mcp-servers/complex-server/bin/server

  # Local server (e.g., Obsidian plugin)
  - name: obsidian-mcp-tools
    command: ~/Obsidian/Digital Garden/.obsidian/plugins/mcp-tools/bin/mcp-server
    env:
      OBSIDIAN_API_KEY: "{{ lookup('vault_secret', 'mcp_secrets.obsidian.digital_garden.api_key') }}"

  # Remove a server
  - name: deprecated-server
    state: absent
    command: placeholder  # Required but not used when state is absent

  # Server for specific config file only
  - name: desktop-only-server
    command: some-command
    config_files:
      - path: "~/Library/Application Support/Claude/claude_desktop_config.json"
        state: present

  # Server with optional deploy target (skipped when parent dir missing)
  - name: cross-tool-server
    command: some-command
    config_files:
      - path: ~/.config/mcp-hub/servers.json
        state: present              # mandatory — dir created if missing
      - path: "~/Library/Application Support/Claude/claude_desktop_config.json"
        state: present
        optional: true               # skipped when Claude Desktop not installed
      - path: ~/Projects/productivity/.mcp.local.json
        state: present
        optional: true               # skipped when sibling repo not cloned
```

### `config_files` options

| Key | Default | Description |
|-----|---------|-------------|
| `path` | — | Target config file path (required). `~` is expanded. |
| `state` | `present` | `present` adds the server entry, `absent` removes it. |
| `optional` | `false` | When `true`, silently skip this path if its parent directory does not exist. Use for paths that depend on optional tools (Claude Desktop, sibling repos). When `false`, the role creates the parent directory if missing and writes the file. `state: absent` entries are always treated as optional — removing from a nonexistent path is a no-op. |

### URL-based Servers (HTTP/SSE transport)

```yaml
mcp_servers:
  # Simple URL-based server
  - name: remote-api
    url: "https://api.example.com/mcp"
    config_files:
      - path: ~/.config/mcp-hub/servers.json
        state: present

  # URL-based server with streamable-http transport and authentication
  - name: authenticated-api
    url: "https://secure.example.com/mcp"
    transport: streamable-http
    headers:
      x-api-key: "{{ lookup('vault_secret', 'mcp_secrets.secure.api_key') }}"
      x-user-id: "user@example.com"
    config_files:
      - path: ~/.config/mcp-hub/servers.json
        state: present

  # URL-based server with 1Password secret in headers
  - name: corporate-mcp
    url: "https://internal.corp.com/api/mcp"
    transport: sse
    headers:
      Authorization: "op://Private/corporate-mcp/token"
      x-employee-id: "12345"
```

## Running the Role

```bash
# Install/update all MCP servers
./dotfiles install mcp-servers

# Or run with ansible directly
ansible-playbook playbook.yml --tags mcp-servers
```

## Generated Config Format

The role generates JSON config files in the standard MCP format:

### Command-based Server

```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "package-name"],
      "env": {
        "API_KEY": "resolved-secret-value"
      }
    }
  }
}
```

### URL-based Server

```json
{
  "mcpServers": {
    "remote-api": {
      "url": "https://api.example.com/mcp"
    },
    "authenticated-api": {
      "url": "https://secure.example.com/mcp",
      "transport": "streamable-http",
      "headers": {
        "x-api-key": "resolved-secret-value",
        "x-user-id": "user@example.com"
      }
    }
  }
}
```

## Notes

- Existing servers in config files that aren't managed by this role are preserved
- Config files with secrets (env vars or headers) automatically get `0600` permissions
- Git repositories are updated on every run (fetch + checkout)
- The `post_clone` command runs in the repository directory after clone/update
- Servers are merged across profiles using the `name` field as the unique key
- URL-based servers don't require command availability checks and are always added to config
- Command-based servers are validated (command must exist) before being added to config

## Safety: Protecting Local Changes

The role protects against accidental data loss in git-cloned MCP servers. Before any destructive operation, it checks for:

1. **Uncommitted changes** (modified/untracked files)
2. **Unpushed commits** (local commits not yet pushed to upstream)

### Protected Operations

The following operations will **fail** if local changes are detected:

- **Remote URL change**: If the configured `git_repo` URL differs from the existing remote, the role would need to delete and re-clone. With local changes, this fails instead.
- **Force checkout**: If `git_force: true` is set, the role would discard local changes during checkout. With local changes, this fails instead.

### Override with `git_force_reset`

To explicitly allow destructive operations and discard local changes, set `git_force_reset: true`:

```yaml
mcp_servers:
  - name: my-server
    git_repo: https://github.com/new-org/my-server  # Changed URL
    git_force_reset: true  # Allow deletion despite local changes
    command: my-server
```

### Example Error

```
TASK [[🤖 MCP] Fail if repo with changed remote has local changes] ***
fatal: [localhost]: FAILED! => {"msg": "MCP server 'my-server' has local changes but remote URL changed.\nCannot safely delete and re-clone without losing local changes.\n\nLocal changes detected:\n M src/main.py\n?? new-file.txt\n\nTo force reset, set 'git_force_reset: true' on this server."}
```

# Secret Management

Secrets (API keys, tokens) are stored encrypted using Ansible Vault in `secrets.yml` files within each profile directory.

## Setup

Create a vault password file (git-ignored):
```bash
echo 'your-password' > .vault_password
chmod 600 .vault_password
```

## CLI Commands

```bash
# Initialize vault password file
./dotfiles secret init

# Set a secret (requires -p profile)
./dotfiles secret set -p common mcp_secrets.myservice.api_key
./dotfiles secret set -p work mcp_secrets.myservice.api_key

# Get a secret (requires -p profile)
./dotfiles secret get -p common mcp_secrets.myservice.api_key

# List all secrets (across all profiles)
./dotfiles secret list

# Edit secrets directly (requires -p profile)
./dotfiles secret edit -p common

# Change vault password (requires -p profile or --all)
./dotfiles secret rekey -p common
./dotfiles secret rekey --all  # Rekey all profiles with secrets
```

## Using Secrets in Configuration

Reference secrets using the custom `vault_secret` lookup plugin:

```yaml
mcp_servers:
  my-server:
    command: npx
    args: ["-y", "my-mcp-server"]
    env:
      API_KEY: "{{ lookup('vault_secret', 'mcp_secrets.myservice.api_key') }}"
```

Secrets are automatically resolved during playbook runs when `.vault_password` exists.

## Secret Files

- `profiles/common/secrets.yml` - Shared secrets for all profiles
- `profiles/work/secrets.yml` - Work profile secrets (optional)
- `profiles/personal/secrets.yml` - Personal profile secrets (optional)
- `profiles/{profile}/secrets.yml` - Private profile secrets (for git-ignored profiles)

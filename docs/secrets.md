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

# Get multiple secrets in a single decrypt (amortizes ansible-vault startup)
./dotfiles secret get -p common key.one key.two key.three

# Get multiple secrets NUL-separated (safe for any byte, including newlines)
./dotfiles secret get -p common -0 key.one key.two key.three

# List all secrets (across all profiles)
./dotfiles secret list

# Edit secrets directly (requires -p profile)
./dotfiles secret edit -p common

# Change vault password (requires -p profile or --all)
./dotfiles secret rekey -p common
./dotfiles secret rekey --all  # Rekey all profiles with secrets
```

Exit codes: `get`/`set`/`edit` exit non-zero on failure, suitable for `set -e` shell pipelines (`VAR="$(./dotfiles secret get -p p key)" || handle_failure`).

## 1Password fallback for vault passwords

Vault-unlock passwords live in the local backend (macOS keychain on Mac, gpg-encrypted file elsewhere). You can optionally mirror them to a single 1Password item and use it as a **read-through fallback** — handy for bootstrapping a new machine or recovering after a local-keychain issue.

### How it works

- Point `DOTFILES_VAULT_OP_ITEM` at a 1Password item reference, e.g.
  ```fish
  set -gx DOTFILES_VAULT_OP_ITEM op://Private/dotfiles-vault-passwords
  ```
- Inside that item, store each profile's vault password in a custom concealed field whose label matches the profile (`agents`, `private-adobe`, `personal-common`, …).
- Optional: set `OP_ACCOUNT` if you're signed into multiple 1Password accounts.

### When 1Password is consulted

1. **Local miss.** If `keychain read <profile>` returns nothing, the CLI reads `op://<item>/<profile>` and writes the value back to the local backend — so the next run is fast and offline.
2. **Decryption failure.** If `ansible-vault` fails with `Decryption failed` (i.e. the locally-cached password is stale), the CLI refreshes from 1Password, writes back to the local backend, and retries the vault operation once.
3. **Manual push/pull.** The `dotfiles secret rekey` flow already writes the new password to the local backend; if you want to push it up to 1Password, do so yourself with `op item edit` — there is no `sync` subcommand (yet).

### What 1Password is **not**

Not a replacement for the local backend at runtime. Every `ansible-playbook` and MCP spawn still reads from the local backend first; `op` is only invoked on a miss. This keeps agent spawns fast and preserves offline operation after the initial pull.

## Using Secrets in Configuration

### Runtime-resolved MCP secrets (preferred for `mcp_servers`)

Use the `secret_env` field. The role rewrites the server's `command`/`args` to call `bin/run-with-secrets.sh`, which fetches secrets at spawn time via `dotfiles secret get`. **The rendered MCP config files contain only the vault key path, never the secret value** — they're safe to commit and survive backup/sync without leaking tokens.

```yaml
mcp_servers:
  - name: my-server
    command: npx
    args: ["-y", "my-mcp-server"]
    env:
      LOG_LEVEL: debug            # plain env stays as-is
    secret_env:
      API_KEY: mcp_secrets.myservice.api_key
      OTHER:   mcp_secrets.myservice.other_token
```

The wrapper does one batched `dotfiles secret get -p <profile> -0 <keys...>` call (one vault decrypt regardless of N secrets). `set -e` in the wrapper aborts before `exec` if any key fails to resolve, so a misconfigured server fails loudly rather than starting with an empty env var.

Limitations:
- Stdio servers only. URL-based servers (`url:` + `headers:`) still use install-time `vault_secret` lookups (see below).
- Requires the repo's `.vault_password` to be readable when servers spawn (no interactive prompt).

### Install-time secrets (legacy / URL servers)

For fields that can't be rewritten at runtime (e.g. HTTP headers on URL-based servers), reference secrets using the `vault_secret` lookup plugin. These values **are** rendered into the config file as plaintext, so the file is chmod 0600 and should be treated accordingly.

```yaml
mcp_servers:
  - name: authenticated-api
    url: "https://secure.example.com/mcp"
    transport: streamable-http
    headers:
      x-api-key: "{{ lookup('vault_secret', 'mcp_secrets.secure.api_key') }}"
```

Secrets are automatically resolved during playbook runs when `.vault_password` exists.

## Secret Files

- `profiles/common/secrets.yml` - Shared secrets for all profiles
- `profiles/work/secrets.yml` - Work profile secrets (optional)
- `profiles/personal/secrets.yml` - Personal profile secrets (optional)
- `profiles/{profile}/secrets.yml` - Private profile secrets (for git-ignored profiles)

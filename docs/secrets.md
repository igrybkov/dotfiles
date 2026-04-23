# Secret Management

Secrets (API keys, tokens) are stored encrypted using Ansible Vault in `secrets.yml` files within each profile directory. The vault password itself lives in the operating system's native credential store — **not** in a file on disk.

## How passwords are stored

| Platform | Backend | Location |
|---|---|---|
| macOS | Login keychain (via the Python `keyring` library) | Service `com.grybkov.dotfiles.vault`, one item per profile label |
| Linux | Single GPG-symmetric-encrypted file, one master password unlocks all entries | `~/.config/dotfiles/vault-secrets.yml.gpg` (mode 600) |

The backend is selected automatically by `sys.platform`; there is no manual toggle.

On macOS, items inherit the login keychain's lock state — unlocked when you're logged in, locked according to your Screen Lock settings. On Linux, the master password is prompted interactively (via `gpg-agent` + pinentry) or supplied via `DOTFILES_VAULT_MASTER_PASSWORD` for unattended runs.

## Initial setup

From a fresh checkout on a macOS or Linux machine:

```bash
./dotfiles secret init
```

This:
1. Ensures the backend is ready (Linux: checks `gpg` is installed; macOS: no-op).
2. Enumerates every profile with an encrypted `secrets.yml`.
3. For each profile, either offers to import the vault password from 1Password (if `op` is installed) or prompts you to enter it. Entered passwords are **validated by decrypting the real secrets file** before being saved — a wrong password re-prompts up to three times.

To provision one label without going through the full list:

```bash
./dotfiles secret keychain push <profile>
```

## Daily-use CLI

```bash
# View backend state + list of stored labels (no values)
./dotfiles secret keychain status

# Refresh stored passwords from 1Password (recovers from stale keychain)
./dotfiles secret keychain pull <profile>
./dotfiles secret keychain pull --all

# Read one secret (defaults to clipboard on TTY, auto-clears after 30s)
./dotfiles secret get -p <profile> mcp_secrets.myservice.api_key

# Read multiple secrets in one decrypt pass
./dotfiles secret get -p <profile> key.one key.two

# Read NUL-separated (safe for any byte, including newlines) → for scripts
./dotfiles secret get -p <profile> -0 key.one key.two

# Force stdout instead of clipboard
./dotfiles secret get -p <profile> --no-clipboard key

# Write a new secret value
./dotfiles secret set -p <profile> mcp_secrets.myservice.api_key

# Edit secrets interactively ($EDITOR over a decrypted copy)
./dotfiles secret edit -p <profile>

# Change vault password for a profile (or all profiles)
./dotfiles secret rekey -p <profile>
./dotfiles secret rekey --all

# List stored-label inventory (no values)
./dotfiles secret list

# Remove a stored password for a label
./dotfiles secret keychain rm <profile>
```

Exit codes: `get`/`set`/`edit` return non-zero on failure, suitable for `set -e` shell pipelines:

```bash
VAR="$(./dotfiles secret get -p private-adobe mcp_secrets.service.token)" || exit 1
```

## 1Password fallback

If you keep a mirror of vault-unlock passwords in 1Password, the CLI can consult it automatically on a miss — useful for bootstrapping a new machine or recovering after a local-keychain issue.

### Setup

Point `DOTFILES_VAULT_OP_ITEM` at a 1Password item reference:

```fish
set -gx DOTFILES_VAULT_OP_ITEM op://Private/dotfiles-vault-passwords
```

Inside that item, store each profile's vault password in a custom **concealed field** whose label matches the profile name (`private-adobe`, `private-personal-productivity`, …).

If you have multiple 1Password accounts signed in, also set `OP_ACCOUNT`.

### When 1Password is consulted

1. **Local miss.** If `keychain read <profile>` returns nothing, the CLI reads `op://<item>/<profile>` and writes the value back to the local backend — so the next run is fast and offline.
2. **Decryption failure.** If decryption fails (i.e. the locally-cached password has gone stale, typically after a rekey on another machine), the tool refreshes from 1Password, writes back, and retries once. This covers both the CLI path (`secret list`/`get`/`edit`) and the `vault_secret` Ansible lookup plugin used at playbook time.
3. **Manual pull.** Run `./dotfiles secret keychain pull <label>` (or `--all`) to explicitly refresh stored passwords from 1Password. The fetched value is validated by decrypting the profile's `secrets.yml` before it overwrites the local backend — a bad field value never replaces a good stored password.
4. **Manual push.** After `secret rekey`, the new password is saved locally. Pushed to 1Password automatically when `DOTFILES_VAULT_OP_ITEM` is set (pass `--no-sync` to skip).

### What 1Password is not

Not a runtime dependency. Every `ansible-playbook` invocation and every MCP-server spawn still reads from the local backend first; `op` is only called on a miss. Agents stay fast, and the system works offline once the local backend is populated.

## Using secrets in configuration

### Runtime-resolved MCP secrets (preferred for `mcp_servers`)

Use the `secret_env` field. The role rewrites the server's `command`/`args` to call `bin/run-with-secrets.sh`, which fetches secrets at spawn time via `dotfiles secret get`. **Rendered MCP config files contain only vault key paths, never the secret values** — safe to commit, safe in backups.

```yaml
mcp_servers:
  - name: my-server
    command: npx
    args: ["-y", "my-mcp-server"]
    env:
      LOG_LEVEL: debug              # plain env stays as-is
    secret_env:
      API_KEY: mcp_secrets.myservice.api_key
      OTHER:   mcp_secrets.myservice.other_token
```

The wrapper does one batched `dotfiles secret get -p <profile> -0 <keys...>` call (one vault decrypt regardless of N secrets). `set -e` in the wrapper aborts before `exec` if any key fails to resolve, so a misconfigured server fails loudly rather than starting with an empty env var.

Limitations:
- Stdio servers only. URL-based servers (`url:` + `headers:`) use install-time `vault_secret` lookups (see below).
- Requires the vault backend to be populated — run `secret init` once per machine.

### Install-time secrets (URL servers, other fields)

For fields that can't be rewritten at runtime (e.g. HTTP headers on URL-based servers), reference secrets using the `vault_secret` lookup plugin. These values **are** rendered into the config file, so the task writes it `0600`.

```yaml
mcp_servers:
  - name: authenticated-api
    url: "https://secure.example.com/mcp"
    transport: streamable-http
    headers:
      x-api-key: "{{ lookup('vault_secret', 'mcp_secrets.secure.api_key') }}"
```

The lookup plugin reads the vault-id label from each file header and invokes `bin/dotfiles-vault-client` to fetch the password from the backend. Tasks that receive the resolved values are marked `no_log: true` so `-vvv` debug output never contains decrypted secrets.

## Ansible integration

`./dotfiles install` sets `ANSIBLE_VAULT_IDENTITY_LIST` to point at `bin/dotfiles-vault-client` for every profile with an encrypted `secrets.yml`. Ansible invokes that script on demand when it hits encrypted content; the script reads from the OS backend.

There are no long-lived password files anywhere in the system. Temporary files are created only in specific CLI flows (e.g. `secret rekey` needs to pass both old and new passwords to `ansible-vault rekey`) and are scoped to a `TemporaryDirectory()` that's cleaned up immediately.

## Secret file layout

- `profiles/common/secrets.yml` — shared secrets (if used)
- `profiles/{profile}/secrets.yml` — per-profile secrets
- `profiles/private/{profile}/secrets.yml` — private-profile secrets (each private profile is its own gitignored repo)

Each file is encrypted with its own vault-id tag matching the profile name (e.g. `$ANSIBLE_VAULT;1.2;AES256;private-adobe`). Rekeying one profile does not affect the others.

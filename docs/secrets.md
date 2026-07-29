# Secret Management

Secrets (API keys, tokens) are stored encrypted with [sops](https://github.com/getsops/sops) using [age](https://github.com/FiloSottile/age) recipients, in `secrets.yml` files within each profile directory. The model is **per-machine keys, per-profile recipient lists** — there is no single global key.

## Architecture

### Per-machine age keypair

Each machine has exactly one age keypair. Its **private key** is stored by the OS-specific backend (`get_backend()`, label `_age_private_key`) and is never written to plaintext on disk or printed. Its **public key** is enrolled — per profile — as a recipient of that profile's secrets.

The backend is selected by platform: the macOS login keychain (service `com.grybkov.dotfiles.vault`, via `keyring`) on macOS, or a GPG-symmetric-encrypted file (`~/.config/dotfiles/vault-secrets.yml.gpg`, unlocked by a master password or `DOTFILES_VAULT_MASTER_PASSWORD`) elsewhere. Same abstraction, no manual toggle.

### Per-profile `.sops.yaml` recipient lists

Every profile that has secrets carries its own `.sops.yaml` (a sibling of its `secrets.yml`, at the profile root). That file lists the age **public keys** allowed to decrypt the profile's `secrets.yml`:

```yaml
# profiles/private/adobe/.sops.yaml
creation_rules:
  - path_regex: secrets\.yml$
    age: >-
      age1machineA...,
      age1machineB...,
      age1escrow...
```

Recipient sets diverge per profile **on purpose**: one profile may list two machines plus the escrow key while another lists a single machine. There is no root or global `.sops.yaml`.

### Opt-in escrow key

Any machine's key can be designated as an **escrow key** by mirroring its private half into a 1Password Secure Note titled `dotfiles-age-key` (`dotfiles secret keychain backup`). The escrow private key lives *only* in 1Password — never in a profile.

A profile trusts the escrow key only when its **public** key has been explicitly enrolled as a recipient. No command ever adds the escrow key to a profile implicitly. Because escrow can always re-key a profile, **losing a previous machine is the normal case** — there is no "old machine helps new machine" handshake to perform. A fresh machine generates its own key and enrolls itself, decrypting for the re-wrap step via the escrow key.

## The invariant: no encrypted secrets in the public repo

The public dotfiles repo **must never track an encrypted secret file.** Encrypted secrets belong only in private profiles, which are gitignored here and each live in their own git repo.

This is enforced by `scripts/check_no_committed_secrets.py` (wired into pre-commit with `pass_filenames: false`, and run in CI). It scans `git ls-files` and rejects any tracked file that is:

1. named `secrets.yml`, or located under a `secrets/` directory, OR
2. Ansible-Vault-encrypted (`$ANSIBLE_VAULT` header), OR
3. sops-encrypted (YAML with a top-level `sops:` mapping — detected with the same `dotfiles_cli.vault.sops.is_sops_encrypted` the CLI uses, so the definitions never drift).

The complementary rule — a private profile's `secrets.yml` must always **be** encrypted — is enforced by a mirror pre-commit hook inside each private profile's own repo.

## Setup on a new machine

```bash
./dotfiles secret init
```

`init`:

1. Looks for this machine's age key in the keychain. If present, it just reports status.
2. If absent, imports one from `--from <path>` (or an interactively supplied path), otherwise generates a fresh keypair. The private key is stored in the keychain; the public key is printed.
3. Reports, per profile with a `.sops.yaml`, whether this machine is already a recipient.

`init` **never** pulls a key from 1Password — the escrow key there is opt-in per profile, not a machine's own identity. To restore a specific key instead of generating one:

```bash
./dotfiles secret init --from ~/backup/age-key.txt   # import an identity file
# or paste an exported key:
./dotfiles secret keychain push                       # reads the key from stdin (Ctrl-D)
```

Then enroll this machine into the profiles you need (next section).

## Enrollment and revocation

### Enroll this machine into a profile

```bash
./dotfiles secret enroll -p <profile>     # one profile
./dotfiles secret enroll --all            # every discovered profile
```

`enroll` adds this machine's public key to the profile's `.sops.yaml`, then runs `sops updatekeys` on the `secrets.yml` so the ciphertext is re-wrapped for the new recipient set. Re-wrapping must first decrypt the file's current data key, so it needs an identity that is *already* a recipient. The identity is chosen by this probe order (each candidate verified with a trial `sops -d`):

1. this machine's keychain key (already a recipient — e.g. re-running enroll),
2. the escrow key from 1Password (only works if the profile enrolled escrow),
3. an age identity file passed with `--identity <path>`.

Flags:

- `--identity <path>` — force a specific age identity file for the decrypt step.
- `--from-escrow` — force using the 1Password escrow key.

If the profile has no ciphertext yet (bootstrap), `enroll` just records the recipient — there is nothing to re-encrypt. If any step fails, the `.sops.yaml` change is rolled back so a recipient is never left listed for ciphertext it can't decrypt.

The escrow / provided key is passed to sops via `SOPS_AGE_KEY` for that one subprocess only — it is never written to the keychain or to disk.

### Revoke a recipient

```bash
./dotfiles secret revoke <age-public-key> -p <profile>
./dotfiles secret revoke <age-public-key> --all
```

`revoke` removes the public key from the profile's `.sops.yaml` and re-keys the `secrets.yml` (same identity fallback / `--identity` / `--from-escrow` options as `enroll`). Future ciphertext can no longer be decrypted by that key.

**Old ciphertext already in git history stays decryptable by the revoked key.** So `revoke` prints the profile's secret key-paths and reminds you to rotate the ones that matter. Rotation itself is manual (`secret set` each value to a fresh secret).

## Day-to-day CLI

```bash
# Set a value (dot-notation key). Requires the profile to be enrolled first.
./dotfiles secret set -p <profile> mcp_secrets.myservice.api_key
echo "value" | ./dotfiles secret set -p <profile> mcp_secrets.myservice.api_key

# Read one secret. Defaults to clipboard (30s auto-clear) on a single-key
# interactive TTY; prints otherwise.
./dotfiles secret get -p <profile> mcp_secrets.myservice.api_key

# Read multiple secrets in one decrypt pass
./dotfiles secret get -p <profile> key.one key.two

# NUL-separated output (byte-safe, for scripts); implies no clipboard
./dotfiles secret get -p <profile> -0 key.one key.two

# Force stdout instead of clipboard
./dotfiles secret get -p <profile> --no-clipboard key

# Edit interactively ($EDITOR over a decrypted copy, re-encrypted on save)
./dotfiles secret edit -p <profile>

# List key-paths (no values). Omit -p to list across all profiles.
./dotfiles secret list -p <profile>
```

`set` requires the profile to already have a `.sops.yaml` (so sops knows who to encrypt for) — run `secret enroll -p <profile>` first if it doesn't.

Exit codes: `get`/`set`/`edit` return non-zero on failure, suitable for `set -e` pipelines:

```bash
VAR="$(./dotfiles secret get -p private-adobe mcp_secrets.service.token)" || exit 1
```

### Keychain management

```bash
./dotfiles secret keychain status        # backend state, this machine's public key, stored labels
./dotfiles secret keychain push          # store an age private key from stdin (import/restore)
./dotfiles secret keychain export-key    # print the private key (to back it up; guarded on a TTY)
./dotfiles secret keychain backup        # designate this key as escrow → 1Password item 'dotfiles-age-key'
./dotfiles secret keychain rm --age      # remove this machine's stored age private key
./dotfiles secret keychain rm <label>    # remove a leftover per-profile Ansible-Vault password (post-migration cleanup)
```

## Using secrets in configuration

### Runtime-resolved MCP secrets (preferred for `mcp_servers`)

Use the `secret_env` field. The `mcp_servers` role rewrites the server's `command`/`args` to call `bin/run-with-secrets.sh`, which fetches secrets at spawn time via `dotfiles secret get`. **Rendered MCP config files contain only key paths, never the secret values** — safe to commit, safe in backups.

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

The wrapper does one batched `dotfiles secret get -p <profile> -0 <keys...>` call (one sops decrypt regardless of N secrets). `set -e` aborts before `exec` if any key fails to resolve, so a misconfigured server fails loudly rather than starting with an empty env var.

#### Cross-profile contributions (preferred)

When one MCP server needs secrets that live across multiple profiles, multiple profiles declare `mcp_servers:` entries with the same `name:`. Exactly one profile is the **owner** — it sets `command:` or `url:` and carries the rest of the shape. Other profiles are **contributors**: partial entries that add extra `secret_env:` / `env:` pairs. The playbook's `merge_mcp_servers` filter collapses them into a single record and auto-applies the cross-profile `@<contributor>` suffix to every contributed `secret_env` value, so profile authors always write bare key paths.

```yaml
# profiles/private/personal/productivity/config.yml — owns `obsidian`
mcp_servers:
  - name: obsidian
    command: obsidian-mcp-server
    secret_env:
      OBSIDIAN_API_KEY_GARDEN: mcp_secrets.obsidian.digital_garden.api_key

# profiles/private/adobe/config.yml — contributes, does NOT own
mcp_servers:
  - name: obsidian
    secret_env:
      OBSIDIAN_API_KEY_ADOBE: mcp_secrets.obsidian_adobe.api_key
```

At install time this renders as one `obsidian` entry with both keys; the rendered `~/.config/mcp-hub/servers.json` carries `OBSIDIAN_API_KEY_ADOBE=mcp_secrets.obsidian_adobe.api_key@private-adobe` on the wrapper command line. Contribution rules:

- **What counts as a contribution.** An entry whose fields are a subset of `{name, secret_env, env}` and that declares at least one `secret_env:`/`env:` pair. Anything else — owners, pruning entries like `name + config_files`, top-level `state: absent`, … — passes through verbatim and never merges.
- **Home-profile contributions stay bare.** A contribution from the same profile that owns the server gets no suffix.
- **Conflicts fail fast.** Two contributors declaring the same env-var name on the same server, or a contributor clashing with the owner's own `secret_env:`, aborts the playbook at aggregation time with both profile names in the error.
- **Orphan contributions fail fast.** A contribution whose `name:` no profile owns aborts with the contributor's profile name.

#### Hand-written `@profile` suffix (lower-level)

For ad-hoc cases that don't warrant splitting across profiles — or for the `vault_secret` Jinja lookup (install-time URL-server headers) — the resolver also accepts an explicit `@profile-name` suffix on any path:

```yaml
env:
  ADOBE_KEY: "{{ lookup('vault_secret', 'mcp_secrets.obsidian_adobe.api_key@private-adobe') }}"
```

The wrapper groups requested keys by profile and does one decrypt per referenced profile. Paths are split at the **last** `@`, so profile names containing `/` work naturally (`key@personal/productivity`). Leave the suffix off to use the server's home profile.

Limitations:
- Stdio servers only. URL-based servers (`url:` + `headers:`) use `secret_headers:` (below).
- Requires this machine's age key to be provisioned and enrolled — run `secret init` + `secret enroll` once per machine.

### Install-time secrets for URL servers (`secret_headers:`)

Runtime rewriting only works for stdio servers. For HTTP headers on URL-based servers, use `secret_headers:` — a header name mapped to a sops key-path (dot notation, optional `@profile` suffix). The `mcp_servers` role resolves each via the `vault_secret` lookup at install time and folds the result into `headers:` in the rendered config, which the task writes `0600`.

```yaml
mcp_servers:
  - name: authenticated-api
    url: "https://secure.example.com/mcp"
    transport: streamable-http
    secret_headers:
      x-api-key: mcp_secrets.secure.api_key      # resolved at install time
```

The secret must hold the **complete** header value (store `Bearer <token>`, not just the token). A header name must not appear in both `headers:` and `secret_headers:` — the role fails fast if it does. Writing a raw `lookup('vault_secret', ...)` expression by hand in `headers:` is no longer the recommended path; `secret_headers:` is the validated equivalent.

## Ansible integration

The `vault_secret` lookup plugin resolves secrets at playbook time. It dispatches on each file's on-disk format:

1. **sops** (top-level `sops:` mapping) — decrypts via the dotfiles_cli sops backend, reading this machine's age key from the keychain (fetched through a fresh subprocess to avoid a fork-after-keychain crash in Ansible workers). This is the current path.
2. **Ansible-Vault** (`$ANSIBLE_VAULT` header) — retained for reading *historical* vault-encrypted files a colleague may still have. The lookup fetches the vault password by shelling out to `bin/dotfiles-vault-client`, with a 1Password stale-password retry. New profiles never produce this format.
3. **Plain YAML** — parsed as-is (legacy or not-yet-encrypted).

Tasks that receive resolved values are marked `no_log: true` so `-vvv` output never contains decrypted secrets. There are no long-lived password files anywhere in the system.

## Secret file layout

- `profiles/{profile}/secrets.yml` + `profiles/{profile}/.sops.yaml` — per-profile secrets and their recipient list
- `profiles/private/{profile}/secrets.yml` — private-profile secrets (each private profile is its own gitignored repo, with its own `.sops.yaml` and its own mirror pre-commit hook enforcing encryption)

Each profile's recipient list is independent — enrolling or revoking a key on one profile does not touch the others.

# Security Policy

## Secret Management

This repository uses multiple layers of security to protect sensitive data.

### Ansible Vault Encryption

Sensitive configuration (API keys, tokens, credentials) is encrypted using [Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/index.html).

**Setup:**

1. Create a vault password file (git-ignored):
   ```bash
   ./dotfiles secret init
   ```

2. Set secrets using the CLI:
   ```bash
   ./dotfiles secret set mcp_secrets.myservice.api_key
   ```

3. Secrets are stored encrypted in `profiles/{profile}/secrets/{profile}.yml`

**Important:** The `.vault_password` file is git-ignored and must NEVER be committed to the repository.

### Dynamic Secret Resolution with 1Password

For personal information (name, email, SSH keys), the system uses 1Password CLI (`op read`) to resolve secrets dynamically at runtime rather than storing them in configuration files.

Example from gitconfig:
```gitconfig
[user]
name = {{ lookup('pipe', 'op read "op://Personal/GitHub/name"') }}
email = {{ lookup('pipe', 'op read "op://Personal/GitHub/email"') }}
```

This ensures sensitive personal data is never stored in the repository, even encrypted.

### Private Profiles

Personal and work-specific configuration should be stored in private profiles under `profiles/private/`:

```bash
# Create a private profile
./dotfiles profile bootstrap mycompany

# This creates profiles/private/mycompany/ which is git-ignored
```

Private profiles can be managed as separate git repositories, allowing you to:
- Keep work configs in a private company repo
- Share the main dotfiles publicly while keeping personal data private
- Separate concerns between different environments

The `profiles/private/` directory is git-ignored by default and will never be committed to the public repository.

## What NOT to Commit

**Never commit these to the repository:**

- `.vault_password` files (vault encryption passwords)
- Unencrypted API keys, tokens, or credentials
- SSH private keys (only public keys, if necessary)
- Personal email addresses or names (use `op read` instead)
- Internal hostnames or IP addresses
- Company-specific configuration (use private profiles)
- 1Password vault item IDs (use in private profiles only)

**Safe to commit:**

- Encrypted `secrets.yml` files (vault-encrypted)
- Public SSH keys referenced via `op read`
- Generic configuration templates
- Public package lists (brew formulae, casks)

## Pre-commit Security Scanning

The repository includes [TruffleHog](https://github.com/trufflesecurity/trufflehog) in pre-commit hooks to detect accidentally committed secrets:

```bash
# Run security scan manually
mise x -- uv run pre-commit run trufflehog --all-files
```

This will catch common patterns like:
- API keys and tokens
- AWS credentials
- Private keys
- Passwords in plaintext

## Reporting Security Issues

If you discover a security vulnerability in this repository, please report it responsibly:

**Preferred:** Use [GitHub Security Advisories](https://github.com/igrybkov/dotfiles/security/advisories/new) for private disclosure

**Alternative:** Open a public issue at https://github.com/igrybkov/dotfiles/issues (for non-sensitive security improvements)

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

We'll respond to security reports as quickly as possible and coordinate disclosure timing with you.

## Security Best Practices

When contributing or forking this repository:

1. **Review before committing:** Use `git diff --staged` to verify no secrets are included
2. **Use vault encryption:** Store all secrets in encrypted `secrets.yml` files
3. **Leverage private profiles:** Keep work/personal config in `profiles/private/`
4. **Use 1Password CLI:** Reference dynamic secrets with `op read` instead of hardcoding
5. **Enable pre-commit hooks:** Run `mise x -- uv run pre-commit install` to catch issues early
6. **Audit your fork:** Run secret scanning tools on your fork before making it public

## Vault Password Management

**Backup your vault passwords securely:**

- Store vault passwords in 1Password, not in plaintext files
- Use different vault passwords for different profiles
- Document which vault password protects which profile's secrets

**Rotating vault passwords:**

```bash
# Change vault password for a specific profile
./dotfiles secret rekey common

# Change vault password for all profiles
./dotfiles secret rekey --all
```

This re-encrypts all secrets with a new password while preserving the data.

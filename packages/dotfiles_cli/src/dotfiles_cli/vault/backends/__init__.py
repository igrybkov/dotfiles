"""Platform-specific vault backend implementations.

Direct import of `macos` is macOS-gated; `gpg_file` is the default elsewhere.
Callers should use `vault.backend.get_backend()` rather than importing
implementations directly.
"""

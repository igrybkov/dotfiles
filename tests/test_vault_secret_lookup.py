"""Tests for the vault_secret Ansible lookup plugin.

Covers the pure-Python helpers (`_parse_term`, `_build_vault_files`,
`_resolve_path`) and the three-way format dispatch in `_decrypt_file`
(Ansible-Vault / sops / plain YAML). The sops and Ansible-Vault branches are
exercised with fixture files plus monkeypatched decrypt steps so no real
`sops` binary, keychain, or vault password is needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLUGIN_DIR = Path(__file__).parent.parent / "ansible_plugins" / "lookup"
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from ansible.errors import AnsibleError  # noqa: E402

import vault_secret  # noqa: E402
from vault_secret import (  # noqa: E402
    LookupModule,
    _build_vault_files,
    _decrypt_file,
    _parse_term,
)


@pytest.fixture(autouse=True)
def _clear_sops_cache(monkeypatch):
    """Drop the module-level sops decrypt cache between tests.

    Also stubs `_get_age_key` so tests never shell out to a real
    `read_age_key_via_subprocess()` (which execs a subprocess and touches the
    real keychain) — the fixture value below documents that fake decrypts
    should always be called with this key.
    """
    vault_secret._sops_decrypt_cached.cache_clear()
    monkeypatch.setattr(vault_secret, "_get_age_key", lambda: "test-age-key")
    yield
    vault_secret._sops_decrypt_cached.cache_clear()


# ---------------------------------------------------------------------------
# _parse_term
# ---------------------------------------------------------------------------


def test_parse_term_no_at():
    assert _parse_term("mcp.github.token") == ("mcp.github.token", None)


def test_parse_term_with_profile():
    assert _parse_term("mcp.github.token@work") == ("mcp.github.token", "work")


def test_parse_term_splits_on_last_at():
    # Profile names may contain '/', and the key path may contain '@'.
    assert _parse_term("weird@path@personal/productivity") == (
        "weird@path",
        "personal/productivity",
    )


def test_parse_term_empty_profile_raises():
    with pytest.raises(AnsibleError):
        _parse_term("key.path@")


def test_parse_term_empty_key_raises():
    with pytest.raises(AnsibleError):
        _parse_term("@profile")


# ---------------------------------------------------------------------------
# _build_vault_files
# ---------------------------------------------------------------------------


def test_build_vault_files_includes_host_and_common(tmp_path):
    (tmp_path / "secrets").mkdir()
    files = _build_vault_files(tmp_path, "myhost", "shell")
    names = [f.name for f in files]
    assert names[0] == "myhost.yml"
    assert names[1] == "common.yml"


def test_build_vault_files_profile_secrets(tmp_path):
    (tmp_path / "secrets").mkdir()
    profile_dir = tmp_path / "profiles" / "shell"
    profile_dir.mkdir(parents=True)
    (profile_dir / "config.yml").write_text("---\n")  # marks a discoverable profile
    (profile_dir / "secrets.yml").write_text("k: v\n")
    files = _build_vault_files(tmp_path, "myhost", "shell")
    assert (profile_dir / "secrets.yml") in files


# ---------------------------------------------------------------------------
# _resolve_path
# ---------------------------------------------------------------------------


def test_resolve_path_nested():
    lm = LookupModule()
    data = {"mcp": {"github": {"token": "abc"}}}
    assert lm._resolve_path(data, "mcp.github.token") == "abc"


def test_resolve_path_missing_returns_none():
    lm = LookupModule()
    assert lm._resolve_path({"mcp": {}}, "mcp.github.token") is None


def test_resolve_path_non_dict_intermediate_returns_none():
    lm = LookupModule()
    assert lm._resolve_path({"mcp": "scalar"}, "mcp.github.token") is None


# ---------------------------------------------------------------------------
# _decrypt_file — three-way format dispatch
# ---------------------------------------------------------------------------


def test_decrypt_file_plain_yaml(tmp_path):
    """A file that is neither vault- nor sops-encrypted is parsed verbatim."""
    f = tmp_path / "secrets.yml"
    f.write_text("mcp:\n  github:\n    token: plain\n")
    result = _decrypt_file(f, tmp_path / "unused-client")
    assert result == {"mcp": {"github": {"token": "plain"}}}


def test_decrypt_file_empty_yaml_returns_empty_dict(tmp_path):
    f = tmp_path / "secrets.yml"
    f.write_text("")
    assert _decrypt_file(f, tmp_path / "unused-client") == {}


def test_decrypt_file_ansible_vault(tmp_path, monkeypatch):
    """Vault-headed files take the Ansible-Vault path (password + VaultLib)."""
    f = tmp_path / "secrets.yml"
    f.write_bytes(b"$ANSIBLE_VAULT;1.1;AES256;work\ndeadbeef\n")

    monkeypatch.setattr(vault_secret, "_fetch_password", lambda script, vid: "pw")

    captured = {}

    def fake_try_decrypt(raw, vault_id, password):
        captured["vault_id"] = vault_id
        return b"api:\n  key: vault-secret\n"

    monkeypatch.setattr(vault_secret, "_try_decrypt", fake_try_decrypt)

    result = _decrypt_file(f, tmp_path / "client")
    assert result == {"api": {"key": "vault-secret"}}
    assert captured["vault_id"] == "work"


def test_decrypt_file_sops(tmp_path, monkeypatch):
    """A YAML file with a top-level `sops:` mapping takes the sops path."""
    f = tmp_path / "secrets.yml"
    f.write_text(
        "mcp:\n"
        "    github:\n"
        "        token: ENC[AES256_GCM,data:xxxx,type:str]\n"
        "sops:\n"
        "    version: 3.9.0\n"
        "    mac: ENC[AES256_GCM,data:yyyy]\n"
    )

    # Real is_sops_encrypted detects the `sops:` mapping (no binary needed);
    # only the decrypt itself is stubbed.
    calls = []

    def fake_decrypt(path, age_key=None):
        calls.append((path, age_key))
        return {"mcp": {"github": {"token": "decrypted-token"}}}

    monkeypatch.setattr(vault_secret._sops, "decrypt_to_dict", fake_decrypt)

    result = _decrypt_file(f, tmp_path / "unused-client")
    assert result == {"mcp": {"github": {"token": "decrypted-token"}}}
    assert calls == [(f.resolve(), "test-age-key")]


def test_decrypt_file_sops_cached_once(tmp_path, monkeypatch):
    """The same sops file is decrypted at most once per process."""
    f = tmp_path / "secrets.yml"
    f.write_text("k: ENC[data]\nsops:\n    version: 3.9.0\n")

    calls = []
    monkeypatch.setattr(
        vault_secret._sops,
        "decrypt_to_dict",
        lambda path, age_key=None: calls.append(path) or {"k": "v"},
    )

    _decrypt_file(f, tmp_path / "c")
    _decrypt_file(f, tmp_path / "c")
    assert len(calls) == 1


def test_decrypt_file_sops_unavailable_falls_back_to_plain(tmp_path, monkeypatch):
    """When the sops backend can't be imported, sops-looking YAML is returned as-is.

    This is the degraded environment where dotfiles_cli is not on the path.
    The file is returned verbatim (ciphertext strings intact) rather than
    crashing — matching the pre-existing plain-YAML fallback contract.
    """
    f = tmp_path / "secrets.yml"
    f.write_text("k: ENC[data]\nsops:\n    version: 3.9.0\n")

    monkeypatch.setattr(vault_secret, "_sops", None)

    result = _decrypt_file(f, tmp_path / "c")
    assert result["k"] == "ENC[data]"
    assert "sops" in result

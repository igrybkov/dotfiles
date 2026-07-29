"""Tests for the sops/age vault backend (per-machine key model)."""

from __future__ import annotations

import subprocess
from unittest.mock import Mock, patch

import pytest

from dotfiles_cli.vault import sops
from dotfiles_cli.vault.age import (
    _find_mise,
    _mise_tool_path,
    generate_keypair,
    get_public_key_from_private,
    is_age_keygen_available,
    is_sops_available,
    resolve_sops,
)
from dotfiles_cli.vault.sops import SopsError

_AGE = "dotfiles_cli.vault.age"


def _make_executable(path):
    """Write a stub file at ``path`` and mark it executable."""
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)


# ===========================================================================
# TestResolveSops — PATH first, then mise (ambient or vendored shim)
# ===========================================================================


class TestResolveSops:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """resolve_sops is lru_cache'd; each test needs a clean slate."""
        resolve_sops.cache_clear()
        yield
        resolve_sops.cache_clear()

    def test_prefers_path_when_sops_present(self):
        with (
            patch(f"{_AGE}.shutil.which", return_value="/usr/bin/sops"),
            patch(f"{_AGE}.subprocess.run") as mock_run,
        ):
            assert resolve_sops() == "/usr/bin/sops"
        mock_run.assert_not_called()

    def test_falls_back_to_ambient_mise(self, tmp_path):
        sops_bin = tmp_path / "sops"
        _make_executable(sops_bin)

        def which_side_effect(name):
            return "/usr/local/bin/mise" if name == "mise" else None

        with (
            patch(f"{_AGE}.shutil.which", side_effect=which_side_effect),
            patch(f"{_AGE}.subprocess.run") as mock_run,
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(tmp_path)),
        ):
            mock_run.return_value = Mock(returncode=0, stdout=f"{tmp_path}\n")
            assert resolve_sops() == str(sops_bin)
            assert is_sops_available() is True

    def test_falls_back_to_vendored_shim(self, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        vendored_mise = bin_dir / "mise"
        _make_executable(vendored_mise)

        sops_install_dir = tmp_path / "installs" / "sops" / "3.13.1"
        sops_install_dir.mkdir(parents=True)
        sops_bin = sops_install_dir / "sops"
        _make_executable(sops_bin)

        with (
            patch(f"{_AGE}.shutil.which", return_value=None),
            patch(f"{_AGE}.subprocess.run") as mock_run,
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(tmp_path)),
        ):
            mock_run.return_value = Mock(returncode=0, stdout=f"{sops_install_dir}\n")
            assert resolve_sops() == str(sops_bin)

        assert mock_run.call_args[0][0][0] == str(vendored_mise)

    def test_returns_none_when_neither_found(self, tmp_path):
        with (
            patch(f"{_AGE}.shutil.which", return_value=None),
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(tmp_path)),
        ):
            assert resolve_sops() is None
            assert is_sops_available() is False

    def test_find_mise_none_without_path_or_vendored(self, tmp_path):
        with (
            patch(f"{_AGE}.shutil.which", return_value=None),
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(tmp_path)),
        ):
            assert _find_mise() is None

    def test_mise_tool_path_none_on_nonzero_exit(self, tmp_path):
        mise = tmp_path / "mise"
        _make_executable(mise)
        with (
            patch(f"{_AGE}.shutil.which", return_value=str(mise)),
            patch(f"{_AGE}.subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="not found")
            assert _mise_tool_path("sops") is None

    def test_mise_tool_path_none_on_timeout(self, tmp_path):
        mise = tmp_path / "mise"
        _make_executable(mise)
        with (
            patch(f"{_AGE}.shutil.which", return_value=str(mise)),
            patch(
                f"{_AGE}.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="mise", timeout=10),
            ),
        ):
            assert _mise_tool_path("sops") is None

    def test_mise_tool_path_none_when_mise_missing(self, tmp_path):
        with (
            patch(f"{_AGE}.shutil.which", return_value=None),
            patch("dotfiles_cli.constants.DOTFILES_DIR", str(tmp_path)),
        ):
            assert _mise_tool_path("sops") is None


# ===========================================================================
# TestSopsEncryptedDetection
# ===========================================================================


class TestSopsEncryptedDetection:
    def test_true_for_sops_metadata(self, tmp_path):
        f = tmp_path / "secrets.yml"
        f.write_text("sops:\n  version: '3.8.0'\nk: ENC[...]\n")
        assert sops.is_sops_encrypted(f) is True

    def test_false_for_plaintext(self, tmp_path):
        f = tmp_path / "secrets.yml"
        f.write_text("k: plaintext\n")
        assert sops.is_sops_encrypted(f) is False

    def test_false_for_missing(self, tmp_path):
        assert sops.is_sops_encrypted(tmp_path / "nope.yml") is False


# ===========================================================================
# TestSopsConfigRecipients — per-profile .sops.yaml add/remove/get
# ===========================================================================


class TestSopsConfigRecipients:
    def _profile_dir(self, tmp_path):
        """Patch get_profile_path so 'alpha' resolves to a tmp profile dir."""
        prof = tmp_path / "profiles" / "alpha"
        prof.mkdir(parents=True)
        return prof

    def test_ensure_sops_config_creates_from_template(self, tmp_path):
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            path = sops.ensure_sops_config("alpha", ["age1a", "age1b"])
            assert path.exists()
            assert sops.get_configured_recipients("alpha") == ["age1a", "age1b"]

    def test_ensure_sops_config_no_op_when_present(self, tmp_path):
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            sops.ensure_sops_config("alpha", ["age1a"])
            # Second call with different recipients must not overwrite.
            sops.ensure_sops_config("alpha", ["age1zzz"])
            assert sops.get_configured_recipients("alpha") == ["age1a"]

    def test_add_recipient_creates_and_appends(self, tmp_path):
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            assert sops.add_sops_recipient("alpha", "age1a") is True  # creates
            assert sops.add_sops_recipient("alpha", "age1b") is True  # appends
            assert sops.get_configured_recipients("alpha") == ["age1a", "age1b"]

    def test_add_recipient_idempotent(self, tmp_path):
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            sops.add_sops_recipient("alpha", "age1a")
            assert sops.add_sops_recipient("alpha", "age1a") is False
            assert sops.get_configured_recipients("alpha") == ["age1a"]

    def test_remove_recipient(self, tmp_path):
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            sops.add_sops_recipient("alpha", "age1a")
            sops.add_sops_recipient("alpha", "age1b")
            assert sops.remove_sops_recipient("alpha", "age1a") is True
            assert sops.get_configured_recipients("alpha") == ["age1b"]

    def test_remove_recipient_absent_is_false(self, tmp_path):
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            sops.add_sops_recipient("alpha", "age1a")
            assert sops.remove_sops_recipient("alpha", "age1missing") is False

    def test_all_creation_rules_get_the_same_set(self, tmp_path):
        """Both template rules must carry identical recipient lists."""
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            sops.add_sops_recipient("alpha", "age1a")
            sops.add_sops_recipient("alpha", "age1b")
            text = sops.get_sops_config_path("alpha").read_text()
        # Two `age:` lines, both listing both recipients.
        age_lines = [ln for ln in text.splitlines() if ln.strip().startswith("age:")]
        assert len(age_lines) == 2
        for ln in age_lines:
            assert "age1a" in ln and "age1b" in ln

    def test_has_sops_config(self, tmp_path):
        prof = self._profile_dir(tmp_path)
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            assert sops.has_sops_config("alpha") is False
            sops.ensure_sops_config("alpha", ["age1a"])
            assert sops.has_sops_config("alpha") is True


# ===========================================================================
# TestSopsRoundTrip — real sops + age (skipped if the tools are unavailable)
# ===========================================================================

_TOOLS_AVAILABLE = is_sops_available() and is_age_keygen_available()


@pytest.mark.skipif(not _TOOLS_AVAILABLE, reason="sops and/or age not installed")
class TestSopsRoundTrip:
    """End-to-end: encrypt with a per-profile .sops.yaml, decrypt, updatekeys."""

    def _setup(self, tmp_path):
        prof = tmp_path / "profiles" / "alpha"
        prof.mkdir(parents=True)
        priv, pub = generate_keypair()
        # Seed a config listing this key as the sole recipient.
        (prof / ".sops.yaml").write_text(
            f'creation_rules:\n  - path_regex: secrets\\.yml$\n    age: "{pub}"\n'
        )
        return prof / "secrets.yml", priv, pub

    def test_write_encrypt_decrypt_cycle(self, tmp_path):
        secrets_file, priv, _pub = self._setup(tmp_path)
        data = {"mcp": {"github": {"token": "hunter2"}}, "flat": "v"}

        sops.write_and_encrypt(secrets_file, data)
        assert sops.is_sops_encrypted(secrets_file)

        got = sops.decrypt_to_dict(secrets_file, age_key=priv)
        assert got == data
        assert sops.can_decrypt(secrets_file, age_key=priv) is True

    def test_decrypt_key_dot_notation(self, tmp_path):
        secrets_file, priv, _pub = self._setup(tmp_path)
        sops.write_and_encrypt(secrets_file, {"mcp": {"github": {"token": "hunter2"}}})
        # decrypt_key resolves the profile to a secrets.yml; point it at ours.
        with patch(
            f"{sops.__name__}.get_profile_path", return_value=secrets_file.parent
        ):
            value = sops.decrypt_key("alpha", "mcp.github.token", age_key=priv)
        assert value == "hunter2"

    def test_add_recipient_then_updatekeys_grants_access(self, tmp_path):
        secrets_file, priv, _pub = self._setup(tmp_path)
        sops.write_and_encrypt(secrets_file, {"k": "v"})

        # A second key that cannot decrypt yet.
        priv2, pub2 = generate_keypair()
        assert sops.can_decrypt(secrets_file, age_key=priv2) is False

        with patch(
            f"{sops.__name__}.get_profile_path", return_value=secrets_file.parent
        ):
            sops.add_sops_recipient("alpha", pub2)
        rc, _, err = sops.reencrypt_with_updated_keys(secrets_file, age_key=priv)
        assert rc == 0, err

        # Now key2 can decrypt; key1 still can too.
        assert sops.can_decrypt(secrets_file, age_key=priv2) is True
        assert sops.can_decrypt(secrets_file, age_key=priv) is True

    def test_revoke_then_updatekeys_removes_access(self, tmp_path):
        secrets_file, priv, pub = self._setup(tmp_path)
        priv2, pub2 = generate_keypair()
        prof = secrets_file.parent
        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            sops.add_sops_recipient("alpha", pub2)
        sops.write_and_encrypt(secrets_file, {"k": "v"})
        assert sops.can_decrypt(secrets_file, age_key=priv2) is True

        with patch(f"{sops.__name__}.get_profile_path", return_value=prof):
            sops.remove_sops_recipient("alpha", pub2)
        rc, _, err = sops.reencrypt_with_updated_keys(secrets_file, age_key=priv)
        assert rc == 0, err

        assert sops.can_decrypt(secrets_file, age_key=priv2) is False
        assert sops.can_decrypt(secrets_file, age_key=priv) is True

    def test_write_and_encrypt_restores_on_failure(self, tmp_path):
        """A broken .sops.yaml (no recipients) must not clobber the prior file."""
        secrets_file, priv, _pub = self._setup(tmp_path)
        sops.write_and_encrypt(secrets_file, {"k": "original"})
        original_bytes = secrets_file.read_bytes()

        # Corrupt the config so the next encrypt fails.
        (secrets_file.parent / ".sops.yaml").write_text(
            "creation_rules:\n  - path_regex: nomatch$\n"
        )
        with pytest.raises(SopsError):
            sops.write_and_encrypt(secrets_file, {"k": "new"})

        # Prior encrypted content preserved; no plaintext left behind.
        assert secrets_file.read_bytes() == original_bytes
        assert sops.decrypt_to_dict(secrets_file, age_key=priv) == {"k": "original"}
        assert not (secrets_file.parent / "secrets.yml.sops-bak").exists()

    def test_public_key_derivation_matches(self, tmp_path):
        priv, pub = generate_keypair()
        assert get_public_key_from_private(priv) == pub

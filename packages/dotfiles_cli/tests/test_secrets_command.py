"""Tests for `dotfiles secret` CLI commands — sops/age backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dotfiles_cli.commands.secrets import secret
from dotfiles_cli.vault.sops import SopsError


# ---------------------------------------------------------------------------
# Helpers shared by multiple test classes
# ---------------------------------------------------------------------------

# Minimal sops-encrypted YAML stub (the metadata is what `is_sops_encrypted`
# looks for — we never parse it in tests because we mock decrypt_to_dict).
SOPS_STUB = "sops:\n  version: '3.8.0'\nsome_key: 'ENC[AES256_GCM,...]'\n"


def _make_secrets_file(tmp_path: Path, content: str = SOPS_STUB) -> Path:
    """Write a fake secrets.yml under a profile directory and return its path."""
    secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    secrets_file.write_text(content)
    return secrets_file


def _base_patches(secrets_file: Path, profile: str = "alpha"):
    """Return always-needed context managers: file resolution + profile choices."""
    return [
        patch(
            "dotfiles_cli.commands.secrets.get_secrets_file",
            return_value=secrets_file,
        ),
        patch(
            "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
            new=property(lambda self: [profile]),
        ),
        # sops is considered available in all tests unless overridden.
        patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
    ]


def _run_get(args, secrets_file: Path, decrypt_dict: dict | None):
    """Invoke `secret get` with a stubbed sops boundary.

    When *decrypt_dict* is None, sops.decrypt_to_dict raises SopsError (simulating
    decryption failure). Otherwise it returns the dict directly.
    """
    runner = CliRunner()
    bp = _base_patches(secrets_file)
    if decrypt_dict is None:
        sops_side_effect = SopsError("decryption failed")
        decrypt_patch = patch(
            "dotfiles_cli.commands.secrets.sops.decrypt_to_dict",
            side_effect=sops_side_effect,
        )
    else:
        decrypt_patch = patch(
            "dotfiles_cli.commands.secrets.sops.decrypt_to_dict",
            return_value=decrypt_dict,
        )

    with bp[0], bp[1], bp[2], decrypt_patch:
        return runner.invoke(secret, args)


# ---------------------------------------------------------------------------
# fake_backend fixture — used by keychain tests
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_backend():
    """Patch the secrets module's get_backend with a MagicMock backend.

    Note: age.py has its own get_backend import. Tests that trigger
    read_age_key / write_age_key / delete_age_key must patch those separately
    (see individual test patches for `dotfiles_cli.commands.secrets.read_age_key` etc.).
    """
    backend = MagicMock()
    backend.status.return_value = {
        "backend": "test-backend",
        "exists": True,
        "labels": ["common", "adobe"],
    }
    backend.list_labels.return_value = ["common", "adobe"]
    backend.read.return_value = "stored-pw"
    with patch("dotfiles_cli.commands.secrets.get_backend", return_value=backend):
        yield backend


# ===========================================================================
# TestSecretGetExitCodes
# ===========================================================================


class TestSecretGetExitCodes:
    """`secret get` must return non-zero on failure so shell `set -e` reacts."""

    def test_missing_file_exits_nonzero(self, tmp_path):
        missing = tmp_path / "no-profile" / "secrets.yml"
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=missing,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
        ):
            result = runner.invoke(secret, ["get", "-p", "alpha", "foo.bar"])
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()

    def test_decrypt_failure_exits_nonzero(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(["get", "-p", "alpha", "foo.bar"], secrets_file, None)
        assert result.exit_code == 1

    def test_missing_key_exits_nonzero(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "not.here"],
            secrets_file,
            {"top": {"nested": "value"}},
        )
        assert result.exit_code == 1

    def test_partial_missing_key_exits_nonzero(self, tmp_path):
        """Batched call: if ANY requested key is missing, exit non-zero."""
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "-0", "top.nested", "top.missing"],
            secrets_file,
            {"top": {"nested": "value"}},
        )
        assert result.exit_code == 1


# ===========================================================================
# TestSecretGetSingleKey
# ===========================================================================


class TestSecretGetSingleKey:
    """Backward-compatible single-key behavior: one value + trailing newline."""

    def test_single_key_newline_separated(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "top.nested"],
            secrets_file,
            {"top": {"nested": "hello"}},
        )
        assert result.exit_code == 0
        assert result.output == "hello\n"

    def test_single_key_with_zero_flag_null_terminated(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "-0", "top.nested"],
            secrets_file,
            {"top": {"nested": "hello"}},
        )
        assert result.exit_code == 0
        assert result.output == "hello\x00"


# ===========================================================================
# TestSecretGetMultipleKeys
# ===========================================================================


class TestSecretGetMultipleKeys:
    """Multiple keys: shared decrypt, separator-delimited output."""

    def test_multiple_keys_newline_separated(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "a.one", "a.two", "a.three"],
            secrets_file,
            {"a": {"one": "first", "two": "second", "three": "third"}},
        )
        assert result.exit_code == 0
        assert result.output == "first\nsecond\nthird\n"

    def test_multiple_keys_zero_separated(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "-0", "a.one", "a.two"],
            secrets_file,
            {"a": {"one": "first", "two": "second"}},
        )
        assert result.exit_code == 0
        assert result.output == "first\x00second\x00"

    def test_values_with_newlines_safe_under_zero(self, tmp_path):
        """A legitimately multi-line secret must not break the -0 framing."""
        secrets_file = _make_secrets_file(tmp_path)
        # YAML block scalar `|\n  line1\n  line2` parses to "line1\nline2\n"
        result = _run_get(
            ["get", "-p", "alpha", "-0", "a.block", "a.simple"],
            secrets_file,
            {"a": {"block": "line1\nline2\n", "simple": "v"}},
        )
        assert result.exit_code == 0
        assert result.output == "line1\nline2\n\x00v\x00"


# ===========================================================================
# TestSecretGetClipboard
# ===========================================================================


class TestSecretGetClipboard:
    """`--clipboard` mode copies and auto-clears instead of printing."""

    def test_clipboard_writes_to_pbcopy(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        captured_writes = []

        def fake_write(cmd, **kwargs):
            captured_writes.append((cmd, kwargs))
            return MagicMock(returncode=0, stderr="")

        with (
            patch(
                "dotfiles_cli.commands.secrets._clipboard_write_command",
                return_value=["pbcopy"],
            ),
            patch(
                "dotfiles_cli.commands.secrets.subprocess.run",
                side_effect=fake_write,
            ),
            patch("dotfiles_cli.commands.secrets.subprocess.Popen") as mock_popen,
        ):
            result = _run_get(
                ["get", "-p", "alpha", "--clipboard", "top.nested"],
                secrets_file,
                {"top": {"nested": "super-secret"}},
            )
        assert result.exit_code == 0, result.output
        # Secret value must not hit stdout; only the status message should appear.
        assert "super-secret" not in result.output
        assert "clipboard" in result.output
        # The clipboard write saw the actual value.
        assert captured_writes
        _, kwargs = captured_writes[-1]
        assert kwargs.get("input") == "super-secret"
        # The clearer was scheduled via Popen.
        mock_popen.assert_called_once()

    def test_clipboard_rejects_multiple_keys(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "--clipboard", "a.one", "a.two"],
            secrets_file,
            {"a": {"one": "first", "two": "second"}},
        )
        assert result.exit_code == 2

    def test_no_clipboard_forces_stdout_even_on_tty(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "--no-clipboard", "top.nested"],
            secrets_file,
            {"top": {"nested": "value"}},
        )
        assert result.exit_code == 0
        assert result.output == "value\n"

    def test_clipboard_unavailable_exits_1(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        with patch(
            "dotfiles_cli.commands.secrets._clipboard_write_command",
            return_value=None,
        ):
            result = _run_get(
                ["get", "-p", "alpha", "--clipboard", "top.nested"],
                secrets_file,
                {"top": {"nested": "v"}},
            )
        assert result.exit_code == 1


# ===========================================================================
# TestSecretSet
# ===========================================================================


class TestSecretSet:
    """`secret set` writes/merges into a sops-encrypted file."""

    def _base(self, tmp_path: Path, sops_encrypted: bool, file_exists: bool):
        """Return (secrets_file, is_sops_encrypted mock return value)."""
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        if file_exists:
            secrets_file.parent.mkdir(parents=True, exist_ok=True)
            secrets_file.write_text(SOPS_STUB if sops_encrypted else "plaintext: val")
        return secrets_file

    def test_fresh_file_creates_nested_dict_and_encrypts(self, tmp_path):
        """New key on a non-existent file → write_and_encrypt called with nested dict."""
        secrets_file = self._base(tmp_path, sops_encrypted=False, file_exists=False)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch(
                "dotfiles_cli.commands.secrets.sops.is_sops_encrypted",
                return_value=False,
            ),
            patch("dotfiles_cli.commands.secrets.sops.write_and_encrypt") as mock_write,
        ):
            result = runner.invoke(
                secret, ["set", "-p", "alpha", "mcp.github.token"], input="mytoken\n"
            )
        assert result.exit_code == 0, result.output
        mock_write.assert_called_once()
        _, call_dict = mock_write.call_args[0]
        assert call_dict == {"mcp": {"github": {"token": "mytoken"}}}

    def test_existing_sops_file_merges_new_key(self, tmp_path):
        """Updating a sops-encrypted file merges the new key into existing dict."""
        secrets_file = self._base(tmp_path, sops_encrypted=True, file_exists=True)
        runner = CliRunner()
        existing = {"mcp": {"github": {"token": "old"}}}
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch(
                "dotfiles_cli.commands.secrets.sops.is_sops_encrypted",
                return_value=True,
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.decrypt_to_dict",
                return_value=existing,
            ),
            patch("dotfiles_cli.commands.secrets.sops.write_and_encrypt") as mock_write,
        ):
            result = runner.invoke(
                secret, ["set", "-p", "alpha", "mcp.github.token"], input="newtoken\n"
            )
        assert result.exit_code == 0, result.output
        _, call_dict = mock_write.call_args[0]
        assert call_dict["mcp"]["github"]["token"] == "newtoken"

    def test_non_sops_existing_file_errors(self, tmp_path):
        """A non-sops file that already exists must produce an error (migrate first)."""
        secrets_file = self._base(tmp_path, sops_encrypted=False, file_exists=True)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch(
                "dotfiles_cli.commands.secrets.sops.is_sops_encrypted",
                return_value=False,
            ),
        ):
            result = runner.invoke(
                secret, ["set", "-p", "alpha", "foo.bar"], input="val\n"
            )
        assert result.exit_code == 1
        assert (
            "not sops-encrypted" in result.stderr or "migrate" in result.stderr.lower()
        )

    def test_empty_value_exits_1(self, tmp_path):
        """Empty value from stdin → exit 1, no write."""
        secrets_file = self._base(tmp_path, sops_encrypted=False, file_exists=False)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch("dotfiles_cli.commands.secrets.sops.write_and_encrypt") as mock_write,
        ):
            result = runner.invoke(
                secret, ["set", "-p", "alpha", "foo.bar"], input="\n"
            )
        assert result.exit_code == 1
        mock_write.assert_not_called()

    def test_sops_unavailable_exits_1(self, tmp_path):
        """When sops is not installed, set must exit 1 with a helpful message."""
        secrets_file = self._base(tmp_path, sops_encrypted=False, file_exists=False)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.secrets.is_sops_available", return_value=False
            ),
        ):
            result = runner.invoke(secret, ["set", "-p", "alpha", "foo"], input="v\n")
        assert result.exit_code == 1
        assert "sops" in result.stderr.lower()


# ===========================================================================
# TestSecretList
# ===========================================================================


class TestSecretList:
    """`secret list` decrypts via sops and prints key paths."""

    def test_lists_keys_for_profile(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch(
                "dotfiles_cli.commands.secrets.sops.is_sops_encrypted",
                return_value=True,
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.decrypt_to_dict",
                return_value={"mcp": {"github": {"token": "t"}, "slack": {"key": "k"}}},
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_all_secret_locations",
                return_value=["alpha"],
            ),
        ):
            result = runner.invoke(secret, ["list", "-p", "alpha"])
        assert result.exit_code == 0
        assert "mcp.github.token" in result.output
        assert "mcp.slack.key" in result.output

    def test_no_secrets_found_message(self, tmp_path):
        """When no profiles have secrets files, show 'No secrets found'."""
        runner = CliRunner()
        with (
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch(
                "dotfiles_cli.commands.secrets.get_all_secret_locations",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=tmp_path / "nonexistent.yml",
            ),
        ):
            result = runner.invoke(secret, ["list"])
        assert result.exit_code == 0
        assert "No secrets found" in result.output

    def test_sops_unavailable_exits_1(self):
        runner = CliRunner()
        with patch(
            "dotfiles_cli.commands.secrets.is_sops_available", return_value=False
        ):
            result = runner.invoke(secret, ["list"])
        assert result.exit_code == 1


# ===========================================================================
# TestSecretEdit
# ===========================================================================


class TestSecretEdit:
    """`secret edit` opens sops in-place editor."""

    def test_edit_existing_file_calls_run_sops_edit(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch(
                "dotfiles_cli.commands.secrets.sops.run_sops_edit", return_value=0
            ) as mock_edit,
            patch.dict("os.environ", {"EDITOR": "vim"}),
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 0
        mock_edit.assert_called_once_with(secrets_file, editor="vim")

    def test_edit_missing_file_creates_then_edits(self, tmp_path):
        """When the file doesn't exist, write_and_encrypt({}) is called first."""
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch("dotfiles_cli.commands.secrets.sops.write_and_encrypt") as mock_write,
            patch(
                "dotfiles_cli.commands.secrets.sops.run_sops_edit", return_value=0
            ) as mock_edit,
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 0
        mock_write.assert_called_once_with(secrets_file, {})
        mock_edit.assert_called_once()

    def test_edit_nonzero_rc_exits_with_that_rc(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch("dotfiles_cli.commands.secrets.sops.run_sops_edit", return_value=2),
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 2

    def test_sops_unavailable_exits_1(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.secrets.is_sops_available", return_value=False
            ),
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 1


# ===========================================================================
# TestSecretRekey
# ===========================================================================


class TestSecretRekey:
    """`secret rekey` re-encrypts sops files to match updated .sops.yaml keys."""

    def _patches_for_rekey(
        self,
        secrets_file: Path,
        age_key: str | None = "AGE-SECRET-KEY-1ABC",
        sops_encrypted: bool = True,
        reencrypt_rc: int = 0,
        profile_names: list[str] | None = None,
    ):
        return [
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_profile_names",
                return_value=profile_names or ["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=age_key),
            patch(
                "dotfiles_cli.commands.secrets.sops.is_sops_encrypted",
                return_value=sops_encrypted,
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.reencrypt_with_updated_keys",
                return_value=(
                    reencrypt_rc,
                    "",
                    "" if reencrypt_rc == 0 else "sops failed",
                ),
            ),
        ]

    def test_requires_profile_or_all(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        ps = self._patches_for_rekey(secrets_file)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
            result = runner.invoke(secret, ["rekey"])
        assert result.exit_code == 1
        assert "required" in result.stderr.lower() or "--all" in result.stderr

    def test_rejects_both_profile_and_all(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        ps = self._patches_for_rekey(secrets_file)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
            result = runner.invoke(secret, ["rekey", "-p", "alpha", "--all"])
        assert result.exit_code == 1
        assert "Cannot specify both" in result.stderr or "both" in result.stderr.lower()

    def test_errors_when_no_age_key_in_keychain(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        ps = self._patches_for_rekey(secrets_file, age_key=None)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
            result = runner.invoke(secret, ["rekey", "-p", "alpha"])
        assert result.exit_code == 1
        assert "age" in result.stderr.lower()

    def test_rekeys_sops_encrypted_profile(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        ps = self._patches_for_rekey(secrets_file)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
            result = runner.invoke(secret, ["rekey", "-p", "alpha"])
        assert result.exit_code == 0
        assert "alpha" in result.output

    def test_skips_non_sops_files(self, tmp_path):
        """When the file exists but is not sops-encrypted, skip it gracefully."""
        secrets_file = _make_secrets_file(tmp_path, content="plaintext: val")
        runner = CliRunner()
        ps = self._patches_for_rekey(secrets_file, sops_encrypted=False)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
            result = runner.invoke(secret, ["rekey", "-p", "alpha"])
        assert result.exit_code == 0
        assert "skip" in result.output.lower()

    def test_propagates_nonzero_reencrypt_rc_as_failure(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        ps = self._patches_for_rekey(secrets_file, reencrypt_rc=1)
        with ps[0], ps[1], ps[2], ps[3], ps[4], ps[5], ps[6]:
            result = runner.invoke(secret, ["rekey", "-p", "alpha"])
        assert result.exit_code == 1

    def test_all_flag_iterates_all_profiles(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        # reencrypt called once per sops-encrypted profile — both "alpha" and "beta"
        reencrypt_calls = []
        with (
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha", "beta"]),
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_profile_names",
                return_value=["alpha", "beta"],
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch("dotfiles_cli.commands.secrets.is_sops_available", return_value=True),
            patch(
                "dotfiles_cli.commands.secrets.read_age_key",
                return_value="AGE-SECRET-KEY-1ABC",
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.is_sops_encrypted",
                return_value=True,
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.reencrypt_with_updated_keys",
                side_effect=lambda _path: reencrypt_calls.append(_path) or (0, "", ""),
            ),
        ):
            result = runner.invoke(secret, ["rekey", "--all"])
        assert result.exit_code == 0
        assert len(reencrypt_calls) == 2


# ===========================================================================
# TestSecretInit
# ===========================================================================


class TestSecretInit:
    """`secret init` generates an age keypair and updates .sops.yaml."""

    def test_errors_when_age_keygen_missing(self):
        runner = CliRunner()
        with patch(
            "dotfiles_cli.commands.secrets.is_age_keygen_available", return_value=False
        ):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 1
        assert "age-keygen" in result.stderr or "age" in result.stderr.lower()

    def test_existing_key_prints_public_key_and_ensures_sops_config(self):
        """When a key already exists, show its public key and update .sops.yaml."""
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=True,
            ),
            patch(
                "dotfiles_cli.commands.secrets.read_age_key",
                return_value="AGE-SECRET-KEY-1EXISTING",
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_public_key_from_private",
                return_value="age1existingpubkey",
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.get_sops_config_path",
                return_value=MagicMock(**{"exists.return_value": True}),
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.get_configured_recipients",
                return_value=["age1existingpubkey"],
            ),
        ):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 0
        assert "age1existingpubkey" in result.output
        assert "already stored" in result.output.lower()

    def test_existing_key_does_not_regenerate(self):
        """If a key is present, generate_keypair must NOT be called."""
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=True,
            ),
            patch(
                "dotfiles_cli.commands.secrets.read_age_key",
                return_value="AGE-SECRET-KEY-1EXISTING",
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_public_key_from_private",
                return_value="age1existingpubkey",
            ),
            patch("dotfiles_cli.commands.secrets.generate_keypair") as mock_generate,
            patch(
                "dotfiles_cli.commands.secrets.sops.get_sops_config_path",
                return_value=MagicMock(**{"exists.return_value": True}),
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.get_configured_recipients",
                return_value=["age1existingpubkey"],
            ),
        ):
            runner.invoke(secret, ["init"])
        mock_generate.assert_not_called()

    def test_fresh_init_generates_stores_and_updates_sops_yaml(self):
        """No existing key → generate, store, and write public key into .sops.yaml."""
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=True,
            ),
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None),
            patch(
                "dotfiles_cli.commands.secrets.generate_keypair",
                return_value=("AGE-SECRET-KEY-1NEW", "age1newpubkey"),
            ),
            patch("dotfiles_cli.commands.secrets.write_age_key") as mock_write,
            patch(
                "dotfiles_cli.commands.secrets.sops.get_sops_config_path",
                return_value=MagicMock(**{"exists.return_value": True}),
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.get_configured_recipients",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.set_sops_recipient"
            ) as mock_set_recipient,
        ):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 0
        mock_write.assert_called_once_with("AGE-SECRET-KEY-1NEW")
        mock_set_recipient.assert_called_once_with("age1newpubkey")
        assert "age1newpubkey" in result.output

    def test_fresh_init_shows_next_steps(self):
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=True,
            ),
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None),
            patch(
                "dotfiles_cli.commands.secrets.generate_keypair",
                return_value=("AGE-SECRET-KEY-1NEW", "age1newpubkey"),
            ),
            patch("dotfiles_cli.commands.secrets.write_age_key"),
            patch(
                "dotfiles_cli.commands.secrets.sops.get_sops_config_path",
                return_value=MagicMock(**{"exists.return_value": True}),
            ),
            patch(
                "dotfiles_cli.commands.secrets.sops.get_configured_recipients",
                return_value=["age1newpubkey"],
            ),
        ):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 0
        assert "Next steps" in result.output

    def test_missing_sops_config_warns_user(self):
        """When .sops.yaml is absent, print a warning but exit 0."""
        runner = CliRunner()
        sops_config_mock = MagicMock()
        sops_config_mock.exists.return_value = False
        with (
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=True,
            ),
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None),
            patch(
                "dotfiles_cli.commands.secrets.generate_keypair",
                return_value=("AGE-SECRET-KEY-1NEW", "age1newpubkey"),
            ),
            patch("dotfiles_cli.commands.secrets.write_age_key"),
            patch(
                "dotfiles_cli.commands.secrets.sops.get_sops_config_path",
                return_value=sops_config_mock,
            ),
        ):
            result = runner.invoke(secret, ["init"])
        # Should still succeed even when .sops.yaml is missing.
        assert result.exit_code == 0
        # The warning goes to stderr.
        assert "sops.yaml" in result.stderr.lower() or "Warning" in result.stderr


# ===========================================================================
# TestKeychainStatus
# ===========================================================================


class TestKeychainStatus:
    def test_prints_backend_and_labels(self, fake_backend: MagicMock):
        runner = CliRunner()
        with (
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None),
        ):
            result = runner.invoke(secret, ["keychain", "status"])
        assert result.exit_code == 0
        assert "test-backend" in result.output
        assert "common" in result.output
        assert "adobe" in result.output

    def test_status_failure_exits_nonzero(self, fake_backend: MagicMock):
        fake_backend.status.side_effect = RuntimeError("cannot read")
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "status"])
        assert result.exit_code == 1

    def test_age_key_present_shows_public_key(self, fake_backend: MagicMock):
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.read_age_key",
                return_value="AGE-SECRET-KEY-1ABC",
            ),
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=True,
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_public_key_from_private",
                return_value="age1pubkey",
            ),
        ):
            result = runner.invoke(secret, ["keychain", "status"])
        assert result.exit_code == 0
        assert "present" in result.output
        assert "age1pubkey" in result.output

    def test_age_key_absent_shows_init_message(self, fake_backend: MagicMock):
        runner = CliRunner()
        with patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None):
            result = runner.invoke(secret, ["keychain", "status"])
        assert result.exit_code == 0
        assert "not stored" in result.output or "secret init" in result.output.lower()


# ===========================================================================
# TestKeychainPush
# ===========================================================================


class TestKeychainPush:
    """`keychain push` reads an age private key from stdin and stores it."""

    def test_stores_key_from_stdin(self, fake_backend: MagicMock):
        """Pipe in a valid age key → write_age_key called once."""
        runner = CliRunner()
        key_text = "# created: 2024-01-01\nAGE-SECRET-KEY-1ABC123\n"
        with (
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None),
            patch("dotfiles_cli.commands.secrets.write_age_key") as mock_write,
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=False,
            ),
        ):
            result = runner.invoke(secret, ["keychain", "push"], input=key_text)
        assert result.exit_code == 0, result.output
        mock_write.assert_called_once_with(key_text.strip())

    def test_rejects_empty_input(self, fake_backend: MagicMock):
        runner = CliRunner()
        with (
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None),
            patch("dotfiles_cli.commands.secrets.write_age_key") as mock_write,
        ):
            result = runner.invoke(secret, ["keychain", "push"], input="")
        assert result.exit_code == 1
        mock_write.assert_not_called()

    def test_rejects_input_without_age_secret_key_marker(self, fake_backend: MagicMock):
        runner = CliRunner()
        with (
            patch("dotfiles_cli.commands.secrets.read_age_key", return_value=None),
            patch("dotfiles_cli.commands.secrets.write_age_key") as mock_write,
        ):
            result = runner.invoke(
                secret, ["keychain", "push"], input="this-is-not-an-age-key\n"
            )
        assert result.exit_code == 1
        assert "AGE-SECRET-KEY-" in result.stderr
        mock_write.assert_not_called()

    def test_confirms_overwrite_when_key_already_stored(self, fake_backend: MagicMock):
        """Existing key prompts confirmation; answer 'y' stores the new key."""
        runner = CliRunner()
        key_text = "AGE-SECRET-KEY-1NEWKEY\n"
        with (
            patch(
                "dotfiles_cli.commands.secrets.read_age_key",
                return_value="AGE-SECRET-KEY-1OLD",
            ),
            patch("dotfiles_cli.commands.secrets.write_age_key") as mock_write,
            patch(
                "dotfiles_cli.commands.secrets.is_age_keygen_available",
                return_value=False,
            ),
        ):
            # First line consumed by the 'Overwrite?' confirm; rest is the key.
            result = runner.invoke(secret, ["keychain", "push"], input=f"y\n{key_text}")
        assert result.exit_code == 0, result.output
        mock_write.assert_called_once()

    def test_declines_overwrite_aborts(self, fake_backend: MagicMock):
        """Answer 'n' to overwrite prompt → abort, write_age_key not called."""
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.read_age_key",
                return_value="AGE-SECRET-KEY-1OLD",
            ),
            patch("dotfiles_cli.commands.secrets.write_age_key") as mock_write,
        ):
            result = runner.invoke(secret, ["keychain", "push"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output
        mock_write.assert_not_called()


# ===========================================================================
# TestKeychainRm
# ===========================================================================


class TestKeychainRm:
    def test_absent_label_is_noop(self, fake_backend: MagicMock):
        fake_backend.list_labels.return_value = []
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "missing"])
        assert result.exit_code == 0
        fake_backend.delete.assert_not_called()

    def test_yes_flag_deletes_label_without_prompt(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "-y", "common"])
        assert result.exit_code == 0
        fake_backend.delete.assert_called_once_with("common")

    def test_prompt_declined_keeps_item(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "common"], input="n\n")
        assert result.exit_code == 0
        fake_backend.delete.assert_not_called()

    def test_age_flag_removes_age_key_via_delete_age_key(self, fake_backend: MagicMock):
        """--age removes the age private key by calling delete_age_key()."""
        from dotfiles_cli.vault.age import AGE_KEY_LABEL

        fake_backend.list_labels.return_value = [AGE_KEY_LABEL]
        runner = CliRunner()
        with patch("dotfiles_cli.commands.secrets.delete_age_key") as mock_del:
            result = runner.invoke(secret, ["keychain", "rm", "--age", "-y"])
        assert result.exit_code == 0, result.output
        mock_del.assert_called_once()

    def test_age_and_label_are_mutually_exclusive(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "--age", "somelabel"])
        assert result.exit_code == 1
        assert "either" in result.stderr.lower() or "not both" in result.stderr.lower()

    def test_no_arg_shows_error(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm"])
        assert result.exit_code == 1
        assert "LABEL" in result.stderr or "--age" in result.stderr

"""Tests for `dotfiles secret` CLI commands — sops/age per-machine backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dotfiles_cli.commands.secrets import _acquire_identity, secret
from dotfiles_cli.vault.sops import SopsError


# ---------------------------------------------------------------------------
# Helpers shared by multiple test classes
# ---------------------------------------------------------------------------

# Minimal sops-encrypted YAML stub (the metadata is what `is_sops_encrypted`
# looks for — we never parse it in tests because we mock decrypt_to_dict).
SOPS_STUB = "sops:\n  version: '3.8.0'\nsome_key: 'ENC[AES256_GCM,...]'\n"

_CMD = "dotfiles_cli.commands.secrets"


def _make_secrets_file(tmp_path: Path, content: str = SOPS_STUB) -> Path:
    """Write a fake secrets.yml under a profile directory and return its path."""
    secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    secrets_file.write_text(content)
    return secrets_file


def _base_patches(secrets_file: Path, profile: str = "alpha"):
    """Return always-needed context managers: file resolution + profile choices."""
    return [
        patch(f"{_CMD}.get_secrets_file", return_value=secrets_file),
        patch(
            f"{_CMD}.SecretLocationChoice.choices",
            new=property(lambda self: [profile]),
        ),
        patch(f"{_CMD}.is_sops_available", return_value=True),
    ]


def _run_get(args, secrets_file: Path, decrypt_dict: dict | None):
    """Invoke `secret get` with a stubbed sops boundary."""
    runner = CliRunner()
    bp = _base_patches(secrets_file)
    if decrypt_dict is None:
        decrypt_patch = patch(
            f"{_CMD}.sops.decrypt_to_dict",
            side_effect=SopsError("decryption failed"),
        )
    else:
        decrypt_patch = patch(f"{_CMD}.sops.decrypt_to_dict", return_value=decrypt_dict)
    with bp[0], bp[1], bp[2], decrypt_patch:
        return runner.invoke(secret, args)


@pytest.fixture
def fake_backend():
    """Patch the secrets module's get_backend with a MagicMock backend."""
    backend = MagicMock()
    backend.status.return_value = {
        "backend": "test-backend",
        "exists": True,
        "labels": ["common", "adobe"],
    }
    backend.list_labels.return_value = ["common", "adobe"]
    backend.read.return_value = "stored-pw"
    with patch(f"{_CMD}.get_backend", return_value=backend):
        yield backend


# ===========================================================================
# TestSecretGet — exit codes, single/multi key, -0 framing, clipboard
# ===========================================================================


class TestSecretGetExitCodes:
    def test_missing_file_exits_nonzero(self, tmp_path):
        missing = tmp_path / "no-profile" / "secrets.yml"
        runner = CliRunner()
        bp = _base_patches(missing)
        with bp[0], bp[1], bp[2]:
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
            ["get", "-p", "alpha", "not.here"], secrets_file, {"top": {"n": "v"}}
        )
        assert result.exit_code == 1

    def test_partial_missing_key_exits_nonzero(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "-0", "top.nested", "top.missing"],
            secrets_file,
            {"top": {"nested": "value"}},
        )
        assert result.exit_code == 1

    def test_sops_unavailable_exits_1(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        with (
            patch(f"{_CMD}.get_secrets_file", return_value=secrets_file),
            patch(
                f"{_CMD}.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(f"{_CMD}.is_sops_available", return_value=False),
        ):
            result = runner.invoke(secret, ["get", "-p", "alpha", "a"])
        assert result.exit_code == 1
        assert "sops" in result.stderr.lower()


class TestSecretGetOutput:
    def test_single_key_newline(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "top.nested"],
            secrets_file,
            {"top": {"nested": "hello"}},
        )
        assert result.exit_code == 0
        assert result.output == "hello\n"

    def test_single_key_zero(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "-0", "top.nested"],
            secrets_file,
            {"top": {"nested": "hello"}},
        )
        assert result.exit_code == 0
        assert result.output == "hello\x00"

    def test_multiple_keys_newline(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "a.one", "a.two", "a.three"],
            secrets_file,
            {"a": {"one": "first", "two": "second", "three": "third"}},
        )
        assert result.exit_code == 0
        assert result.output == "first\nsecond\nthird\n"

    def test_multiple_keys_zero(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "-0", "a.one", "a.two"],
            secrets_file,
            {"a": {"one": "first", "two": "second"}},
        )
        assert result.exit_code == 0
        assert result.output == "first\x00second\x00"

    def test_multiline_value_safe_under_zero(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "-0", "a.block", "a.simple"],
            secrets_file,
            {"a": {"block": "line1\nline2\n", "simple": "v"}},
        )
        assert result.exit_code == 0
        assert result.output == "line1\nline2\n\x00v\x00"


class TestSecretGetClipboard:
    def test_clipboard_writes_to_pbcopy(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        captured = []

        def fake_write(cmd, **kwargs):
            captured.append((cmd, kwargs))
            return MagicMock(returncode=0, stderr="")

        with (
            patch(f"{_CMD}._clipboard_write_command", return_value=["pbcopy"]),
            patch(f"{_CMD}.subprocess.run", side_effect=fake_write),
            patch(f"{_CMD}.subprocess.Popen") as mock_popen,
        ):
            result = _run_get(
                ["get", "-p", "alpha", "--clipboard", "top.nested"],
                secrets_file,
                {"top": {"nested": "super-secret"}},
            )
        assert result.exit_code == 0, result.output
        assert "super-secret" not in result.output
        assert "clipboard" in result.output
        assert captured and captured[-1][1].get("input") == "super-secret"
        mock_popen.assert_called_once()

    def test_clipboard_rejects_multiple_keys(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        result = _run_get(
            ["get", "-p", "alpha", "--clipboard", "a.one", "a.two"],
            secrets_file,
            {"a": {"one": "first", "two": "second"}},
        )
        assert result.exit_code == 2

    def test_no_clipboard_forces_stdout(self, tmp_path):
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
        with patch(f"{_CMD}._clipboard_write_command", return_value=None):
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
    def _run(self, tmp_path, *, file_exists, sops_encrypted, has_config, input_):
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        if file_exists:
            secrets_file.parent.mkdir(parents=True, exist_ok=True)
            secrets_file.write_text(SOPS_STUB if sops_encrypted else "plain: v")
        runner = CliRunner()
        with (
            patch(f"{_CMD}.get_secrets_file", return_value=secrets_file),
            patch(
                f"{_CMD}.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(f"{_CMD}.is_sops_available", return_value=True),
            patch(f"{_CMD}.sops.has_sops_config", return_value=has_config),
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=sops_encrypted),
            patch(f"{_CMD}.sops.write_and_encrypt") as mock_write,
            patch(f"{_CMD}.sops.decrypt_to_dict", return_value={"mcp": {"t": "old"}}),
        ):
            result = runner.invoke(
                secret, ["set", "-p", "alpha", "mcp.github.token"], input=input_
            )
        return result, mock_write

    def test_fresh_file_creates_nested_dict(self, tmp_path):
        result, mock_write = self._run(
            tmp_path,
            file_exists=False,
            sops_encrypted=False,
            has_config=True,
            input_="mytoken\n",
        )
        assert result.exit_code == 0, result.output
        mock_write.assert_called_once()
        _, call_dict = mock_write.call_args[0]
        assert call_dict == {"mcp": {"github": {"token": "mytoken"}}}

    def test_existing_sops_file_merges(self, tmp_path):
        result, mock_write = self._run(
            tmp_path,
            file_exists=True,
            sops_encrypted=True,
            has_config=True,
            input_="newtoken\n",
        )
        assert result.exit_code == 0, result.output
        _, call_dict = mock_write.call_args[0]
        assert call_dict["mcp"]["github"]["token"] == "newtoken"

    def test_no_sops_config_errors(self, tmp_path):
        result, mock_write = self._run(
            tmp_path,
            file_exists=False,
            sops_encrypted=False,
            has_config=False,
            input_="v\n",
        )
        assert result.exit_code == 1
        assert "enroll" in result.stderr.lower()
        mock_write.assert_not_called()

    def test_non_sops_existing_file_errors(self, tmp_path):
        result, mock_write = self._run(
            tmp_path,
            file_exists=True,
            sops_encrypted=False,
            has_config=True,
            input_="v\n",
        )
        assert result.exit_code == 1
        assert "not sops-encrypted" in result.stderr
        mock_write.assert_not_called()

    def test_empty_value_exits_1(self, tmp_path):
        result, mock_write = self._run(
            tmp_path,
            file_exists=False,
            sops_encrypted=False,
            has_config=True,
            input_="\n",
        )
        assert result.exit_code == 1
        mock_write.assert_not_called()

    def test_sops_unavailable_exits_1(self, tmp_path):
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        runner = CliRunner()
        with (
            patch(f"{_CMD}.get_secrets_file", return_value=secrets_file),
            patch(
                f"{_CMD}.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(f"{_CMD}.is_sops_available", return_value=False),
        ):
            result = runner.invoke(secret, ["set", "-p", "alpha", "foo"], input="v\n")
        assert result.exit_code == 1
        assert "sops" in result.stderr.lower()


# ===========================================================================
# TestSecretList
# ===========================================================================


class TestSecretList:
    def test_lists_keys_for_profile(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        bp = _base_patches(secrets_file)
        with (
            bp[0],
            bp[1],
            bp[2],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=True),
            patch(
                f"{_CMD}.sops.decrypt_to_dict",
                return_value={"mcp": {"github": {"token": "t"}, "slack": {"key": "k"}}},
            ),
            patch(f"{_CMD}.get_all_secret_locations", return_value=["alpha"]),
        ):
            result = runner.invoke(secret, ["list", "-p", "alpha"])
        assert result.exit_code == 0
        assert "mcp.github.token" in result.output
        assert "mcp.slack.key" in result.output

    def test_no_secrets_found(self, tmp_path):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_sops_available", return_value=True),
            patch(f"{_CMD}.get_all_secret_locations", return_value=["alpha"]),
            patch(
                f"{_CMD}.get_secrets_file",
                return_value=tmp_path / "nonexistent.yml",
            ),
        ):
            result = runner.invoke(secret, ["list"])
        assert result.exit_code == 0
        assert "No secrets found" in result.output

    def test_sops_unavailable_exits_1(self):
        runner = CliRunner()
        with patch(f"{_CMD}.is_sops_available", return_value=False):
            result = runner.invoke(secret, ["list"])
        assert result.exit_code == 1


# ===========================================================================
# TestSecretEdit
# ===========================================================================


class TestSecretEdit:
    def test_edit_existing_calls_run_sops_edit(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        bp = _base_patches(secrets_file)
        with (
            bp[0],
            bp[1],
            bp[2],
            patch(f"{_CMD}.sops.has_sops_config", return_value=True),
            patch(f"{_CMD}.sops.run_sops_edit", return_value=0) as mock_edit,
            patch.dict("os.environ", {"EDITOR": "vim"}),
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 0
        mock_edit.assert_called_once_with(secrets_file, editor="vim")

    def test_edit_missing_file_creates_then_edits(self, tmp_path):
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        runner = CliRunner()
        bp = _base_patches(secrets_file)
        with (
            bp[0],
            bp[1],
            bp[2],
            patch(f"{_CMD}.sops.has_sops_config", return_value=True),
            patch(f"{_CMD}.sops.write_and_encrypt") as mock_write,
            patch(f"{_CMD}.sops.run_sops_edit", return_value=0) as mock_edit,
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 0
        mock_write.assert_called_once_with(secrets_file, {})
        mock_edit.assert_called_once()

    def test_edit_no_config_errors(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        bp = _base_patches(secrets_file)
        with (
            bp[0],
            bp[1],
            bp[2],
            patch(f"{_CMD}.sops.has_sops_config", return_value=False),
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 1
        assert "enroll" in result.stderr.lower()

    def test_edit_nonzero_rc_propagates(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        bp = _base_patches(secrets_file)
        with (
            bp[0],
            bp[1],
            bp[2],
            patch(f"{_CMD}.sops.has_sops_config", return_value=True),
            patch(f"{_CMD}.sops.run_sops_edit", return_value=2),
        ):
            result = runner.invoke(secret, ["edit", "-p", "alpha"])
        assert result.exit_code == 2


# ===========================================================================
# TestAcquireIdentity — the three-tier fallback
# ===========================================================================


class TestAcquireIdentity:
    MACHINE = "AGE-SECRET-KEY-1MACHINE\n"
    ESCROW = "AGE-SECRET-KEY-1ESCROW\n"

    def test_machine_key_preferred(self, tmp_path):
        f = _make_secrets_file(tmp_path)
        with (
            patch(f"{_CMD}.read_age_key", return_value=self.MACHINE),
            patch(f"{_CMD}.read_age_key_from_op", return_value=self.ESCROW),
            patch(f"{_CMD}.sops.can_decrypt", return_value=True) as cd,
        ):
            key, source = _acquire_identity("alpha", f)
        assert key == self.MACHINE
        assert "keychain" in source
        cd.assert_called_once_with(f, self.MACHINE)

    def test_falls_through_to_escrow(self, tmp_path):
        f = _make_secrets_file(tmp_path)

        def can(_path, key):
            return key == self.ESCROW

        with (
            patch(f"{_CMD}.read_age_key", return_value=self.MACHINE),
            patch(f"{_CMD}.read_age_key_from_op", return_value=self.ESCROW),
            patch(f"{_CMD}.sops.can_decrypt", side_effect=can),
        ):
            key, source = _acquire_identity("alpha", f)
        assert key == self.ESCROW
        assert "escrow" in source.lower()

    def test_force_escrow_only_tries_escrow(self, tmp_path):
        f = _make_secrets_file(tmp_path)
        with (
            patch(f"{_CMD}.read_age_key", return_value=self.MACHINE) as machine,
            patch(f"{_CMD}.read_age_key_from_op", return_value=self.ESCROW),
            patch(f"{_CMD}.sops.can_decrypt", return_value=True),
        ):
            key, source = _acquire_identity("alpha", f, force_escrow=True)
        assert key == self.ESCROW
        machine.assert_not_called()

    def test_force_escrow_without_op_key_raises(self, tmp_path):
        f = _make_secrets_file(tmp_path)
        with (
            patch(f"{_CMD}.read_age_key_from_op", return_value=None),
            patch(f"{_CMD}.sops.can_decrypt", return_value=True),
        ):
            with pytest.raises(SopsError):
                _acquire_identity("alpha", f, force_escrow=True)

    def test_identity_path_used_and_read(self, tmp_path):
        f = _make_secrets_file(tmp_path)
        id_file = tmp_path / "id.txt"
        id_file.write_text(self.ESCROW)
        with (
            patch(f"{_CMD}.read_age_key", return_value=self.MACHINE) as machine,
            patch(f"{_CMD}.sops.can_decrypt", return_value=True),
        ):
            key, source = _acquire_identity("alpha", f, identity_path=str(id_file))
        assert key == self.ESCROW
        assert str(id_file) in source
        machine.assert_not_called()

    def test_identity_path_bad_content_raises(self, tmp_path):
        f = _make_secrets_file(tmp_path)
        id_file = tmp_path / "id.txt"
        id_file.write_text("not-an-age-key")
        with pytest.raises(SopsError):
            _acquire_identity("alpha", f, identity_path=str(id_file))

    def test_no_identity_works_raises(self, tmp_path):
        f = _make_secrets_file(tmp_path)
        with (
            patch(f"{_CMD}.read_age_key", return_value=self.MACHINE),
            patch(f"{_CMD}.read_age_key_from_op", return_value=None),
            patch(f"{_CMD}.sops.can_decrypt", return_value=False),
        ):
            with pytest.raises(SopsError) as exc:
                _acquire_identity("alpha", f)
        assert "no usable identity" in str(exc.value).lower()

    def test_escrow_key_never_persisted_to_keychain(self, tmp_path):
        """Escrow is passed transiently; it must never hit the machine keychain."""
        f = _make_secrets_file(tmp_path)

        def can(_path, key):
            return key == self.ESCROW

        with (
            patch(f"{_CMD}.read_age_key", return_value=self.MACHINE),
            patch(f"{_CMD}.read_age_key_from_op", return_value=self.ESCROW),
            patch(f"{_CMD}.sops.can_decrypt", side_effect=can),
            patch(f"{_CMD}.write_age_key") as mock_write,
        ):
            _acquire_identity("alpha", f)
        mock_write.assert_not_called()


# ===========================================================================
# TestSecretEnroll
# ===========================================================================


class TestSecretEnroll:
    PUB = "age1machinepub"

    def _common(self, secrets_file: Path):
        return [
            patch(f"{_CMD}.get_secrets_file", return_value=secrets_file),
            patch(
                f"{_CMD}.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(f"{_CMD}.is_sops_available", return_value=True),
            patch(f"{_CMD}.is_age_keygen_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value="AGE-SECRET-KEY-1M"),
            patch(f"{_CMD}.get_public_key_from_private", return_value=self.PUB),
        ]

    def test_no_machine_key_errors(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file)
        with c[0], c[1], c[2], c[3], patch(f"{_CMD}.read_age_key", return_value=None):
            result = runner.invoke(secret, ["enroll", "-p", "alpha"])
        assert result.exit_code == 1
        assert "init" in result.stderr.lower()

    def test_bootstrap_no_ciphertext_just_adds_recipient(self, tmp_path):
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"  # absent
        runner = CliRunner()
        c = self._common(secrets_file)
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            c[4],
            c[5],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=False),
            patch(f"{_CMD}.sops.add_sops_recipient", return_value=True) as add,
            patch(f"{_CMD}.sops.reencrypt_with_updated_keys") as reenc,
        ):
            result = runner.invoke(secret, ["enroll", "-p", "alpha"])
        assert result.exit_code == 0, result.output
        add.assert_called_once_with("alpha", self.PUB)
        reenc.assert_not_called()
        assert "Enrolled" in result.output

    def test_with_ciphertext_runs_updatekeys(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file)
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            c[4],
            c[5],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=True),
            patch(f"{_CMD}.sops.add_sops_recipient", return_value=True),
            patch(
                f"{_CMD}._acquire_identity",
                return_value=("AGE-SECRET-KEY-1M", "this machine's keychain key"),
            ),
            patch(
                f"{_CMD}.sops.reencrypt_with_updated_keys",
                return_value=(0, "", ""),
            ) as reenc,
        ):
            result = runner.invoke(secret, ["enroll", "-p", "alpha"])
        assert result.exit_code == 0, result.output
        reenc.assert_called_once()
        assert "Enrolled" in result.output

    def test_already_recipient_skips_updatekeys(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file)
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            c[4],
            c[5],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=True),
            patch(f"{_CMD}.sops.add_sops_recipient", return_value=False),
            patch(f"{_CMD}.sops.reencrypt_with_updated_keys") as reenc,
        ):
            result = runner.invoke(secret, ["enroll", "-p", "alpha"])
        assert result.exit_code == 0, result.output
        reenc.assert_not_called()
        assert "Already a recipient" in result.output

    def test_acquire_failure_rolls_back(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file)
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            c[4],
            c[5],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=True),
            patch(f"{_CMD}.sops.add_sops_recipient", return_value=True),
            patch(f"{_CMD}._acquire_identity", side_effect=SopsError("no identity")),
            patch(f"{_CMD}.sops.remove_sops_recipient") as remove,
        ):
            result = runner.invoke(secret, ["enroll", "-p", "alpha"])
        assert result.exit_code == 1
        remove.assert_called_once_with("alpha", self.PUB)

    def test_reencrypt_failure_rolls_back(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file)
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            c[4],
            c[5],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=True),
            patch(f"{_CMD}.sops.add_sops_recipient", return_value=True),
            patch(
                f"{_CMD}._acquire_identity",
                return_value=("AGE-SECRET-KEY-1M", "src"),
            ),
            patch(
                f"{_CMD}.sops.reencrypt_with_updated_keys",
                return_value=(1, "", "boom"),
            ),
            patch(f"{_CMD}.sops.remove_sops_recipient") as remove,
        ):
            result = runner.invoke(secret, ["enroll", "-p", "alpha"])
        assert result.exit_code == 1
        remove.assert_called_once_with("alpha", self.PUB)


# ===========================================================================
# TestSecretRevoke
# ===========================================================================


class TestSecretRevoke:
    PUB = "age1revokeme"

    def _common(self, secrets_file: Path, recipients):
        return [
            patch(f"{_CMD}.get_secrets_file", return_value=secrets_file),
            patch(
                f"{_CMD}.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(f"{_CMD}.is_sops_available", return_value=True),
            patch(f"{_CMD}.sops.get_configured_recipients", return_value=recipients),
        ]

    def test_not_a_recipient_reports(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file, recipients=["age1other"])
        with c[0], c[1], c[2], c[3]:
            result = runner.invoke(secret, ["revoke", self.PUB, "-p", "alpha"])
        assert result.exit_code == 0
        assert "Not a recipient" in result.output

    def test_revoke_with_ciphertext_updates_and_lists_rotation(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file, recipients=[self.PUB, "age1keep"])
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=True),
            patch(
                f"{_CMD}._acquire_identity",
                return_value=("AGE-SECRET-KEY-1KEEP", "this machine's keychain key"),
            ),
            patch(
                f"{_CMD}.sops.decrypt_to_dict",
                return_value={"mcp": {"github": {"token": "t"}}},
            ),
            patch(f"{_CMD}.sops.remove_sops_recipient") as remove,
            patch(
                f"{_CMD}.sops.reencrypt_with_updated_keys",
                return_value=(0, "", ""),
            ) as reenc,
        ):
            result = runner.invoke(secret, ["revoke", self.PUB, "-p", "alpha"])
        assert result.exit_code == 0, result.output
        remove.assert_called_once_with("alpha", self.PUB)
        reenc.assert_called_once()
        assert "Revoked" in result.output
        assert "mcp.github.token" in result.output

    def test_reencrypt_failure_rolls_back(self, tmp_path):
        secrets_file = _make_secrets_file(tmp_path)
        runner = CliRunner()
        c = self._common(secrets_file, recipients=[self.PUB, "age1keep"])
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=True),
            patch(
                f"{_CMD}._acquire_identity",
                return_value=("AGE-SECRET-KEY-1KEEP", "src"),
            ),
            patch(f"{_CMD}.sops.decrypt_to_dict", return_value={}),
            patch(f"{_CMD}.sops.remove_sops_recipient"),
            patch(
                f"{_CMD}.sops.reencrypt_with_updated_keys",
                return_value=(1, "", "boom"),
            ),
            patch(f"{_CMD}.sops.add_sops_recipient") as add,
        ):
            result = runner.invoke(secret, ["revoke", self.PUB, "-p", "alpha"])
        assert result.exit_code == 1
        add.assert_called_once_with("alpha", self.PUB)

    def test_no_ciphertext_just_removes(self, tmp_path):
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"  # absent
        runner = CliRunner()
        c = self._common(secrets_file, recipients=[self.PUB])
        with (
            c[0],
            c[1],
            c[2],
            c[3],
            patch(f"{_CMD}.sops.is_sops_encrypted", return_value=False),
            patch(f"{_CMD}.sops.remove_sops_recipient") as remove,
            patch(f"{_CMD}.sops.reencrypt_with_updated_keys") as reenc,
        ):
            result = runner.invoke(secret, ["revoke", self.PUB, "-p", "alpha"])
        assert result.exit_code == 0, result.output
        remove.assert_called_once_with("alpha", self.PUB)
        reenc.assert_not_called()

    def test_requires_profile_or_all(self):
        runner = CliRunner()
        with patch(f"{_CMD}.is_sops_available", return_value=True):
            result = runner.invoke(secret, ["revoke", self.PUB])
        assert result.exit_code == 1
        assert "required" in result.stderr.lower() or "--all" in result.stderr


# ===========================================================================
# TestSecretInit — per-machine
# ===========================================================================


class TestSecretInit:
    def test_errors_when_age_keygen_missing(self):
        runner = CliRunner()
        with patch(f"{_CMD}.is_age_keygen_available", return_value=False):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 1
        assert "age" in result.stderr.lower()

    def test_existing_key_reports_enrollment(self):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_age_keygen_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value="AGE-SECRET-KEY-1E"),
            patch(f"{_CMD}.get_public_key_from_private", return_value="age1pub"),
            patch(f"{_CMD}.sops.get_profiles_with_sops_config", return_value=["alpha"]),
            patch(f"{_CMD}.sops.get_configured_recipients", return_value=["age1pub"]),
            patch(f"{_CMD}.generate_keypair") as gen,
        ):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 0
        assert "already stored" in result.output.lower()
        assert "age1pub" in result.output
        assert "enrolled" in result.output.lower()
        gen.assert_not_called()

    def test_fresh_generate_stores_and_reports(self):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_age_keygen_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value=None),
            patch(
                f"{_CMD}.generate_keypair",
                return_value=("AGE-SECRET-KEY-1NEW", "age1newpub"),
            ),
            patch(f"{_CMD}.write_age_key") as mock_write,
            patch(f"{_CMD}.sops.get_profiles_with_sops_config", return_value=[]),
        ):
            result = runner.invoke(secret, ["init"], input="\n")
        assert result.exit_code == 0, result.output
        mock_write.assert_called_once_with("AGE-SECRET-KEY-1NEW")
        assert "age1newpub" in result.output
        assert "Next steps" in result.output

    def test_import_from_path(self, tmp_path):
        id_file = tmp_path / "id.txt"
        id_file.write_text("# comment\nAGE-SECRET-KEY-1IMPORTED\n")
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_age_keygen_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value=None),
            patch(
                f"{_CMD}.get_public_key_from_private", return_value="age1importedpub"
            ),
            patch(f"{_CMD}.write_age_key") as mock_write,
            patch(f"{_CMD}.generate_keypair") as gen,
            patch(f"{_CMD}.sops.get_profiles_with_sops_config", return_value=[]),
        ):
            result = runner.invoke(secret, ["init", "--from", str(id_file)])
        assert result.exit_code == 0, result.output
        gen.assert_not_called()
        mock_write.assert_called_once()
        assert "age1importedpub" in result.output

    def test_import_from_bad_path_errors(self, tmp_path):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_age_keygen_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value=None),
        ):
            result = runner.invoke(
                secret, ["init", "--from", str(tmp_path / "missing.txt")]
            )
        assert result.exit_code == 1

    def test_does_not_pull_from_1password(self):
        """Per-machine init must never read a key out of 1Password."""
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_age_keygen_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value=None),
            patch(
                f"{_CMD}.generate_keypair",
                return_value=("AGE-SECRET-KEY-1NEW", "age1newpub"),
            ),
            patch(f"{_CMD}.write_age_key"),
            patch(f"{_CMD}.sops.get_profiles_with_sops_config", return_value=[]),
            patch(f"{_CMD}.read_age_key_from_op") as op_read,
        ):
            runner.invoke(secret, ["init"], input="\n")
        op_read.assert_not_called()


# ===========================================================================
# TestKeychain — status / push / backup / export-key / rm
# ===========================================================================


class TestKeychainStatus:
    def test_prints_backend_and_labels(self, fake_backend):
        runner = CliRunner()
        with patch(f"{_CMD}.read_age_key", return_value=None):
            result = runner.invoke(secret, ["keychain", "status"])
        assert result.exit_code == 0
        assert "test-backend" in result.output
        assert "common" in result.output

    def test_age_key_present_shows_public(self, fake_backend):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.read_age_key", return_value="AGE-SECRET-KEY-1A"),
            patch(f"{_CMD}.is_age_keygen_available", return_value=True),
            patch(f"{_CMD}.get_public_key_from_private", return_value="age1pub"),
        ):
            result = runner.invoke(secret, ["keychain", "status"])
        assert result.exit_code == 0
        assert "present" in result.output
        assert "age1pub" in result.output

    def test_status_failure_exits_nonzero(self, fake_backend):
        fake_backend.status.side_effect = RuntimeError("cannot read")
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "status"])
        assert result.exit_code == 1


class TestKeychainPush:
    def test_stores_key_from_stdin(self, fake_backend):
        runner = CliRunner()
        key_text = "# created\nAGE-SECRET-KEY-1ABC\n"
        with (
            patch(f"{_CMD}.read_age_key", return_value=None),
            patch(f"{_CMD}.write_age_key") as mock_write,
            patch(f"{_CMD}.is_age_keygen_available", return_value=False),
        ):
            result = runner.invoke(secret, ["keychain", "push"], input=key_text)
        assert result.exit_code == 0, result.output
        mock_write.assert_called_once_with(key_text.strip())

    def test_rejects_non_age_input(self, fake_backend):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.read_age_key", return_value=None),
            patch(f"{_CMD}.write_age_key") as mock_write,
        ):
            result = runner.invoke(secret, ["keychain", "push"], input="not-a-key\n")
        assert result.exit_code == 1
        assert "AGE-SECRET-KEY-" in result.stderr
        mock_write.assert_not_called()

    def test_declines_overwrite(self, fake_backend):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.read_age_key", return_value="AGE-SECRET-KEY-1OLD"),
            patch(f"{_CMD}.write_age_key") as mock_write,
        ):
            result = runner.invoke(secret, ["keychain", "push"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output
        mock_write.assert_not_called()


class TestKeychainBackup:
    def test_backup_writes_to_op_as_escrow(self, fake_backend):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_op_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value="AGE-SECRET-KEY-1A"),
            patch(f"{_CMD}.write_age_key_to_op") as mock_op,
        ):
            result = runner.invoke(secret, ["keychain", "backup"])
        assert result.exit_code == 0
        mock_op.assert_called_once_with("AGE-SECRET-KEY-1A")
        assert "escrow" in result.output.lower()

    def test_backup_no_op_errors(self, fake_backend):
        runner = CliRunner()
        with patch(f"{_CMD}.is_op_available", return_value=False):
            result = runner.invoke(secret, ["keychain", "backup"])
        assert result.exit_code == 1

    def test_backup_no_key_errors(self, fake_backend):
        runner = CliRunner()
        with (
            patch(f"{_CMD}.is_op_available", return_value=True),
            patch(f"{_CMD}.read_age_key", return_value=None),
        ):
            result = runner.invoke(secret, ["keychain", "backup"])
        assert result.exit_code == 1


class TestKeychainExportKey:
    def test_prints_key_when_not_tty(self, fake_backend):
        runner = CliRunner()
        with patch(f"{_CMD}.read_age_key", return_value="AGE-SECRET-KEY-1A"):
            result = runner.invoke(secret, ["keychain", "export-key"])
        assert result.exit_code == 0
        assert "AGE-SECRET-KEY-1A" in result.output

    def test_absent_key_errors(self, fake_backend):
        runner = CliRunner()
        with patch(f"{_CMD}.read_age_key", return_value=None):
            result = runner.invoke(secret, ["keychain", "export-key"])
        assert result.exit_code == 1


class TestKeychainRm:
    def test_age_flag_removes_age_key(self, fake_backend):
        from dotfiles_cli.vault.age import AGE_KEY_LABEL

        fake_backend.list_labels.return_value = [AGE_KEY_LABEL]
        runner = CliRunner()
        with patch(f"{_CMD}.delete_age_key") as mock_del:
            result = runner.invoke(secret, ["keychain", "rm", "--age", "-y"])
        assert result.exit_code == 0, result.output
        mock_del.assert_called_once()

    def test_label_removes_backend_item(self, fake_backend):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "-y", "common"])
        assert result.exit_code == 0
        fake_backend.delete.assert_called_once_with("common")

    def test_age_and_label_mutually_exclusive(self, fake_backend):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "--age", "somelabel"])
        assert result.exit_code == 1

    def test_no_arg_errors(self, fake_backend):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm"])
        assert result.exit_code == 1

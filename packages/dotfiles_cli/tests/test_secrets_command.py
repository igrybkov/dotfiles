"""Tests for `dotfiles secret` CLI commands — exit codes and batching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dotfiles_cli.commands.secrets import secret
from dotfiles_cli.vault.backends import onepassword


ENCRYPTED_STUB = "$ANSIBLE_VAULT;1.1;AES256\ndummy"


def _setup_profile(tmp_path: Path, yaml_body: str) -> Path:
    """Write a (fake) encrypted secrets.yml and return the path."""
    secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
    secrets_file.parent.mkdir(parents=True)
    secrets_file.write_text(ENCRYPTED_STUB)
    return secrets_file


def _patches(secrets_file: Path, decrypt_body: str | None, profile: str = "alpha"):
    """Patch the CLI's IO boundaries: file resolution, decrypt subprocess, profile choice."""
    ctx = [
        patch(
            "dotfiles_cli.commands.secrets.get_secrets_file",
            return_value=secrets_file,
        ),
        patch(
            "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
            new=property(lambda self: [profile]),
        ),
    ]
    if decrypt_body is None:
        ctx.append(
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
                return_value=(1, "", "decryption failed"),
            )
        )
    else:
        ctx.append(
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
                return_value=(0, decrypt_body, ""),
            )
        )
    return ctx


def _run(args, secrets_file, decrypt_body):
    runner = CliRunner()
    with (
        _patches(secrets_file, decrypt_body)[0],
        _patches(secrets_file, decrypt_body)[1],
        _patches(secrets_file, decrypt_body)[2],
    ):
        return runner.invoke(secret, args)


class TestSecretGetExitCodes:
    """`secret get` must return non-zero on failure so shell `set -e` reacts."""

    def test_missing_file_exits_nonzero(self, tmp_path):
        missing = tmp_path / "no-profile" / "secrets.yml"
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=missing,
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(secret, ["get", "-p", "alpha", "foo.bar"])
        assert result.exit_code == 1
        assert (
            "not found" in result.stderr.lower() or "not found" in result.output.lower()
        )

    def test_decrypt_failure_exits_nonzero(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "foo.bar"], secrets_file, decrypt_body=None
        )
        assert result.exit_code == 1

    def test_missing_key_exits_nonzero(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "not.here"],
            secrets_file,
            decrypt_body="top:\n  nested: value\n",
        )
        assert result.exit_code == 1

    def test_partial_missing_key_exits_nonzero(self, tmp_path):
        """Batched call: if ANY requested key is missing, exit non-zero."""
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "-0", "top.nested", "top.missing"],
            secrets_file,
            decrypt_body="top:\n  nested: value\n",
        )
        assert result.exit_code == 1


class TestSecretGetSingleKey:
    """Backward-compatible single-key behavior: one value + trailing newline."""

    def test_single_key_newline_separated(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "top.nested"],
            secrets_file,
            decrypt_body="top:\n  nested: hello\n",
        )
        assert result.exit_code == 0
        # click's CliRunner captures stdout as text; exact bytes are preserved.
        assert result.output == "hello\n"

    def test_single_key_with_zero_flag_null_terminated(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "-0", "top.nested"],
            secrets_file,
            decrypt_body="top:\n  nested: hello\n",
        )
        assert result.exit_code == 0
        assert result.output == "hello\x00"


class TestSecretGetMultipleKeys:
    """Multiple keys: shared decrypt, separator-delimited output."""

    def test_multiple_keys_newline_separated(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "a.one", "a.two", "a.three"],
            secrets_file,
            decrypt_body="a:\n  one: first\n  two: second\n  three: third\n",
        )
        assert result.exit_code == 0
        assert result.output == "first\nsecond\nthird\n"

    def test_multiple_keys_zero_separated(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "-0", "a.one", "a.two"],
            secrets_file,
            decrypt_body="a:\n  one: first\n  two: second\n",
        )
        assert result.exit_code == 0
        assert result.output == "first\x00second\x00"

    def test_values_with_newlines_safe_under_zero(self, tmp_path):
        """A legitimately multi-line secret must not break the -0 framing."""
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "-0", "a.block", "a.simple"],
            secrets_file,
            decrypt_body="a:\n  block: |\n    line1\n    line2\n  simple: v\n",
        )
        assert result.exit_code == 0
        # Block scalar preserves internal newlines; -0 separator keeps frames distinct.
        assert result.output == "line1\nline2\n\x00v\x00"


class TestSecretGetClipboard:
    """`--clipboard` mode copies and auto-clears instead of printing."""

    def test_clipboard_writes_to_pbcopy(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
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
            result = _run(
                ["get", "-p", "alpha", "--clipboard", "top.nested"],
                secrets_file,
                decrypt_body="top:\n  nested: super-secret\n",
            )
        assert result.exit_code == 0, result.output
        # Secret value must not hit the captured output (CliRunner combines
        # stdout+stderr). Only the status message should appear.
        assert "super-secret" not in result.output
        assert "clipboard" in result.output
        # The clipboard write saw the actual value.
        assert captured_writes
        _, kwargs = captured_writes[-1]
        assert kwargs.get("input") == "super-secret"
        # The clearer was scheduled via Popen.
        mock_popen.assert_called_once()

    def test_clipboard_rejects_multiple_keys(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "--clipboard", "a.one", "a.two"],
            secrets_file,
            decrypt_body="a:\n  one: first\n  two: second\n",
        )
        assert result.exit_code == 2

    def test_no_clipboard_forces_stdout_even_on_tty(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        result = _run(
            ["get", "-p", "alpha", "--no-clipboard", "top.nested"],
            secrets_file,
            decrypt_body="top:\n  nested: value\n",
        )
        assert result.exit_code == 0
        assert result.output == "value\n"

    def test_clipboard_unavailable_exits_1(self, tmp_path):
        secrets_file = _setup_profile(tmp_path, "")
        with patch(
            "dotfiles_cli.commands.secrets._clipboard_write_command",
            return_value=None,
        ):
            result = _run(
                ["get", "-p", "alpha", "--clipboard", "top.nested"],
                secrets_file,
                decrypt_body="top:\n  nested: v\n",
            )
        assert result.exit_code == 1


# ------------------------------------------------------------- keychain subgroup


@pytest.fixture
def fake_backend():
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


class TestKeychainStatus:
    def test_prints_backend_and_labels(self, fake_backend: MagicMock):
        runner = CliRunner()
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


class TestKeychainPush:
    def test_push_writes_after_confirm(self, fake_backend: MagicMock):
        runner = CliRunner()
        # Matches getpass.getpass and its confirm.
        with patch("getpass.getpass", side_effect=["pw", "pw"]):
            result = runner.invoke(secret, ["keychain", "push", "common"])
        assert result.exit_code == 0, result.output
        fake_backend.ensure_ready.assert_called_once()
        fake_backend.write.assert_called_once_with("common", "pw")

    def test_push_rejects_mismatched_confirm(self, fake_backend: MagicMock):
        runner = CliRunner()
        with patch("getpass.getpass", side_effect=["pw", "different"]):
            result = runner.invoke(secret, ["keychain", "push", "common"])
        assert result.exit_code == 1
        fake_backend.write.assert_not_called()

    def test_push_rejects_empty(self, fake_backend: MagicMock):
        runner = CliRunner()
        with patch("getpass.getpass", side_effect=["", ""]):
            result = runner.invoke(secret, ["keychain", "push", "common"])
        assert result.exit_code == 1
        fake_backend.write.assert_not_called()


class TestKeychainPull:
    """`keychain pull` refreshes stored passwords from 1Password."""

    def test_requires_label_or_all(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "pull"])
        assert result.exit_code == 1
        assert "LABEL" in result.output or "--all" in result.output
        fake_backend.write.assert_not_called()

    def test_rejects_label_with_all(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "pull", "-a", "common"])
        assert result.exit_code == 1
        fake_backend.write.assert_not_called()

    def test_aborts_when_1p_not_configured(self, fake_backend: MagicMock):
        runner = CliRunner()
        with patch.object(onepassword, "is_configured", return_value=False):
            result = runner.invoke(secret, ["keychain", "pull", "common"])
        assert result.exit_code == 1
        assert "DOTFILES_VAULT_OP_ITEM" in result.output
        fake_backend.write.assert_not_called()

    def test_pull_single_label_writes_backend(self, fake_backend: MagicMock, tmp_path):
        encrypted = tmp_path / "secrets.yml"
        encrypted.write_text("$ANSIBLE_VAULT;1.1;AES256\nstub")
        runner = CliRunner()
        with (
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(onepassword, "read_field", return_value="fresh-pw"),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=encrypted,
            ),
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
                return_value=(0, "ok", ""),
            ) as mock_vault,
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
        ):
            result = runner.invoke(secret, ["keychain", "pull", "common"])
        assert result.exit_code == 0, result.output
        # Validation uses the fetched password as an explicit one.
        assert mock_vault.call_args.kwargs.get("password") == "fresh-pw"
        fake_backend.write.assert_called_once_with("common", "fresh-pw")

    def test_pull_skips_when_1p_has_no_value(self, fake_backend: MagicMock, tmp_path):
        runner = CliRunner()
        with (
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(onepassword, "read_field", return_value=None),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
        ):
            result = runner.invoke(secret, ["keychain", "pull", "common"])
        assert result.exit_code == 1
        fake_backend.write.assert_not_called()

    def test_pull_skips_when_validation_fails(self, fake_backend: MagicMock, tmp_path):
        """Bad 1P value must not overwrite a (possibly good) stored password."""
        encrypted = tmp_path / "secrets.yml"
        encrypted.write_text("$ANSIBLE_VAULT;1.1;AES256\nstub")
        runner = CliRunner()
        with (
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(onepassword, "read_field", return_value="stale"),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=encrypted,
            ),
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
                return_value=(1, "", "decryption failed"),
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
        ):
            result = runner.invoke(secret, ["keychain", "pull", "common"])
        assert result.exit_code == 1
        fake_backend.write.assert_not_called()

    def test_pull_all_iterates_profiles_with_secrets(
        self, fake_backend: MagicMock, tmp_path
    ):
        encrypted = tmp_path / "secrets.yml"
        encrypted.write_text("$ANSIBLE_VAULT;1.1;AES256\nstub")
        runner = CliRunner()
        with (
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(onepassword, "read_field", side_effect=["pw-a", "pw-b"]),
            patch(
                "dotfiles_cli.commands.secrets.get_profiles_with_secrets",
                return_value=["alpha", "beta"],
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=encrypted,
            ),
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
                return_value=(0, "ok", ""),
            ),
        ):
            result = runner.invoke(secret, ["keychain", "pull", "-a"])
        assert result.exit_code == 0, result.output
        assert fake_backend.write.call_count == 2
        fake_backend.write.assert_any_call("alpha", "pw-a")
        fake_backend.write.assert_any_call("beta", "pw-b")

    def test_pull_skips_validation_when_no_encrypted_file(
        self, fake_backend: MagicMock, tmp_path
    ):
        """A label without an encrypted secrets.yml is trusted as-fetched."""
        missing = tmp_path / "nope.yml"
        runner = CliRunner()
        with (
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(onepassword, "read_field", return_value="pw"),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=missing,
            ),
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
            ) as mock_vault,
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
        ):
            result = runner.invoke(secret, ["keychain", "pull", "common"])
        assert result.exit_code == 0, result.output
        mock_vault.assert_not_called()
        fake_backend.write.assert_called_once_with("common", "pw")


class TestKeychainRm:
    def test_absent_label_is_noop(self, fake_backend: MagicMock):
        fake_backend.list_labels.return_value = []
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "missing"])
        assert result.exit_code == 0
        fake_backend.delete.assert_not_called()

    def test_yes_flag_deletes_without_prompt(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "-y", "common"])
        assert result.exit_code == 0
        fake_backend.delete.assert_called_once_with("common")

    def test_prompt_declined_keeps_item(self, fake_backend: MagicMock):
        runner = CliRunner()
        result = runner.invoke(secret, ["keychain", "rm", "common"], input="n\n")
        assert result.exit_code == 0
        fake_backend.delete.assert_not_called()


# ----------------------------------------------------------------- secret init


class TestSecretInit:
    def test_init_aborts_on_backend_setup_failure(self, fake_backend: MagicMock):
        fake_backend.ensure_ready.side_effect = RuntimeError("gpg missing")
        runner = CliRunner()
        with patch(
            "dotfiles_cli.commands.secrets.get_profiles_with_secrets",
            return_value=[],
        ):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 1
        assert "gpg missing" in result.output

    def test_init_single_label_no_validation_when_file_missing(
        self, fake_backend: MagicMock, tmp_path
    ):
        """Label with no encrypted secrets.yml → accept password as-entered."""
        fake_backend.list_labels.return_value = []
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_profiles_with_secrets",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
            patch("dotfiles_cli.commands.secrets.shutil.which", return_value=None),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=tmp_path / "nonexistent.yml",
            ),
            patch("getpass.getpass", return_value="pw-value"),
        ):
            result = runner.invoke(secret, ["init", "-p", "common"])
        assert result.exit_code == 0, result.output
        fake_backend.ensure_ready.assert_called_once()
        fake_backend.write.assert_called_once_with("common", "pw-value")

    def test_init_validates_against_encrypted_file(
        self, fake_backend: MagicMock, tmp_path
    ):
        """When secrets.yml is encrypted, validate the password by decrypt."""
        fake_backend.list_labels.return_value = []
        encrypted_file = tmp_path / "secrets.yml"
        encrypted_file.write_text("$ANSIBLE_VAULT;1.1;AES256\nciphertext")
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_profiles_with_secrets",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
            patch("dotfiles_cli.commands.secrets.shutil.which", return_value=None),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=encrypted_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
                return_value=(0, "decrypted", ""),
            ) as mock_vault,
            patch("getpass.getpass", return_value="correct-pw"),
        ):
            result = runner.invoke(secret, ["init", "-p", "common"])
        assert result.exit_code == 0, result.output
        fake_backend.write.assert_called_once_with("common", "correct-pw")
        mock_vault.assert_called_once()
        assert mock_vault.call_args.kwargs.get("password") == "correct-pw"

    def test_init_rejects_wrong_password_and_reprompts(
        self, fake_backend: MagicMock, tmp_path
    ):
        """Wrong password → re-prompt; eventually give up after max attempts."""
        fake_backend.list_labels.return_value = []
        encrypted_file = tmp_path / "secrets.yml"
        encrypted_file.write_text("$ANSIBLE_VAULT;1.1;AES256\nciphertext")
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_profiles_with_secrets",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
            patch("dotfiles_cli.commands.secrets.shutil.which", return_value=None),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=encrypted_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.run_ansible_vault",
                return_value=(1, "", "decryption failed"),
            ),
            patch("getpass.getpass", return_value="wrong-pw"),
        ):
            result = runner.invoke(secret, ["init", "-p", "common"])
        # Label skipped (write never called); overall exit still 0.
        assert result.exit_code == 0
        fake_backend.write.assert_not_called()
        assert "Too many failed attempts" in result.output

    def test_init_skips_when_user_declines_overwrite(self, fake_backend: MagicMock):
        fake_backend.list_labels.return_value = ["common"]
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_profiles_with_secrets",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["common"]),
            ),
            patch("dotfiles_cli.commands.secrets.shutil.which", return_value=None),
        ):
            result = runner.invoke(secret, ["init", "-p", "common"], input="n\n")
        assert result.exit_code == 0
        fake_backend.write.assert_not_called()

    def test_init_skips_common_when_no_secrets_file(self, fake_backend: MagicMock):
        """Without -p, only profiles with encrypted secrets are provisioned."""
        fake_backend.list_labels.return_value = []
        runner = CliRunner()
        with (
            patch(
                "dotfiles_cli.commands.secrets.get_profiles_with_secrets",
                return_value=[],
            ),
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: []),
            ),
        ):
            result = runner.invoke(secret, ["init"])
        assert result.exit_code == 0
        assert "nothing to provision" in result.output
        fake_backend.write.assert_not_called()


class TestSecretRekeyOnePasswordSync:
    """`rekey` mirrors the new password to 1Password when configured."""

    @staticmethod
    def _setup_rekey(tmp_path: Path, fake_backend: MagicMock):
        """Shared fixture: encrypted secrets file + stubbed rekey subprocess."""
        secrets_file = tmp_path / "profiles" / "alpha" / "secrets.yml"
        secrets_file.parent.mkdir(parents=True)
        secrets_file.write_text("$ANSIBLE_VAULT;1.1;AES256\nstub")

        return [
            patch(
                "dotfiles_cli.commands.secrets.SecretLocationChoice.choices",
                new=property(lambda self: ["alpha"]),
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_profile_names",
                return_value=["alpha"],
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_secrets_file",
                return_value=secrets_file,
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_vault_password",
                return_value="old-pw",
            ),
            patch(
                "dotfiles_cli.commands.secrets.get_backend",
                return_value=fake_backend,
            ),
            patch(
                "dotfiles_cli.commands.secrets.getpass.getpass",
                side_effect=["new-pw", "new-pw"],
            ),
            patch(
                "dotfiles_cli.commands.secrets.subprocess.run",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ),
        ]

    def test_push_to_1p_when_configured(self, tmp_path: Path):
        fake_backend = MagicMock()
        patches = self._setup_rekey(tmp_path, fake_backend)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(onepassword, "write_field") as write_field,
        ):
            runner = CliRunner()
            result = runner.invoke(secret, ["rekey", "-p", "alpha"])

        assert result.exit_code == 0
        fake_backend.write.assert_called_once_with("alpha", "new-pw")
        write_field.assert_called_once_with("alpha", "new-pw")
        assert "Pushed new password for 'alpha' to 1Password" in result.output

    def test_no_push_when_1p_not_configured(self, tmp_path: Path):
        fake_backend = MagicMock()
        patches = self._setup_rekey(tmp_path, fake_backend)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch.object(onepassword, "is_configured", return_value=False),
            patch.object(onepassword, "write_field") as write_field,
        ):
            runner = CliRunner()
            result = runner.invoke(secret, ["rekey", "-p", "alpha"])

        assert result.exit_code == 0
        write_field.assert_not_called()

    def test_no_sync_flag_skips_push(self, tmp_path: Path):
        fake_backend = MagicMock()
        patches = self._setup_rekey(tmp_path, fake_backend)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(onepassword, "write_field") as write_field,
        ):
            runner = CliRunner()
            result = runner.invoke(secret, ["rekey", "-p", "alpha", "--no-sync"])

        assert result.exit_code == 0
        write_field.assert_not_called()

    def test_1p_failure_warns_but_does_not_fail_rekey(self, tmp_path: Path):
        fake_backend = MagicMock()
        patches = self._setup_rekey(tmp_path, fake_backend)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
            patch.object(onepassword, "is_configured", return_value=True),
            patch.object(
                onepassword,
                "write_field",
                side_effect=onepassword.OnePasswordError("permission denied"),
            ),
        ):
            runner = CliRunner()
            result = runner.invoke(secret, ["rekey", "-p", "alpha"])

        assert result.exit_code == 0
        fake_backend.write.assert_called_once_with("alpha", "new-pw")
        # Warning should reach the user without failing the rekey.
        combined = result.output + result.stderr
        assert "could not push 'alpha' to 1Password" in combined
        assert "permission denied" in combined

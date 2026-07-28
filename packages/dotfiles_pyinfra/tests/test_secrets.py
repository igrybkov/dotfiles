"""Tests for the build-time sops secret reader."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dotfiles_pyinfra import secrets


@pytest.fixture(autouse=True)
def clear_caches() -> None:
    secrets.decrypt_key.cache_clear()
    secrets._profile_secrets_files.cache_clear()


def make_repo(tmp_path: Path) -> Path:
    """A minimal dotfiles tree: one profile with a secrets.yml, one without."""
    withsec = tmp_path / "profiles" / "withsec"
    withsec.mkdir(parents=True)
    (withsec / "config.yml").write_text("profile:\n  priority: 100\n")
    (withsec / "secrets.yml").write_text("a: ENC[...]\n")
    nosec = tmp_path / "profiles" / "nosec"
    nosec.mkdir(parents=True)
    (nosec / "config.yml").write_text("profile:\n  priority: 100\n")
    return tmp_path


def test_dot_to_extract() -> None:
    assert secrets._dot_to_extract("a.b.c") == '["a"]["b"]["c"]'
    with pytest.raises(ValueError):
        secrets._dot_to_extract("")


def test_returns_none_without_age_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.delenv("SOPS_AGE_KEY", raising=False)
    monkeypatch.delenv("SOPS_AGE_KEY_FILE", raising=False)
    assert secrets.decrypt_key("withsec", "a", repo) is None


def test_returns_none_for_profile_without_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("SOPS_AGE_KEY", "AGE-SECRET-KEY-TEST")
    assert secrets.decrypt_key("nosec", "a", repo) is None
    assert secrets.decrypt_key("unknown-profile", "a", repo) is None


def test_successful_extract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("SOPS_AGE_KEY", "AGE-SECRET-KEY-TEST")
    seen_cmds: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="tok-value\n", stderr="")

    monkeypatch.setattr(secrets.subprocess, "run", fake_run)
    assert secrets.decrypt_key("withsec", "svc.token", repo) == "tok-value"
    assert seen_cmds[0][:4] == ["sops", "-d", "--extract", '["svc"]["token"]']

    # Cached: a second call must not spawn another subprocess.
    assert secrets.decrypt_key("withsec", "svc.token", repo) == "tok-value"
    assert len(seen_cmds) == 1


def test_failed_extract_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("SOPS_AGE_KEY", "AGE-SECRET-KEY-TEST")
    monkeypatch.setattr(
        secrets.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom"),
    )
    assert secrets.decrypt_key("withsec", "missing.key", repo) is None


def test_missing_sops_binary_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = make_repo(tmp_path)
    monkeypatch.setenv("SOPS_AGE_KEY", "AGE-SECRET-KEY-TEST")

    def raise_fnf(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("sops")

    monkeypatch.setattr(secrets.subprocess, "run", raise_fnf)
    assert secrets.decrypt_key("withsec", "a", repo) is None

"""Tests for the mcp_servers deploy's build-time logic.

Covers the cross-profile merge (``secret_headers`` handling) and the
build-time resolution of ``secret_headers`` into a rendered headers dict.
The pyinfra operations themselves are exercised by integration runs, not
here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dotfiles_pyinfra.deploys import mcp_servers


def owner(name: str = "srv", profile: str = "own", **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "url": "https://example.test/mcp",
        "_profile": profile,
        **extra,
    }


# ---------------------------------------------------------------------------
# _merge_mcp_servers: secret_headers
# ---------------------------------------------------------------------------


def test_merge_secret_headers_contribution_folds_into_owner() -> None:
    entries = [
        owner(),
        {
            "name": "srv",
            "secret_headers": {"Authorization": "svc.token"},
            "_profile": "contrib",
        },
    ]
    (merged,) = mcp_servers._merge_mcp_servers(entries)
    assert merged["secret_headers"] == {"Authorization": "svc.token@contrib"}


def test_merge_secret_headers_same_profile_gets_no_suffix() -> None:
    entries = [
        owner(),
        {
            "name": "srv",
            "secret_headers": {"Authorization": "svc.token"},
            "_profile": "own",
        },
    ]
    (merged,) = mcp_servers._merge_mcp_servers(entries)
    assert merged["secret_headers"] == {"Authorization": "svc.token"}


def test_merge_secret_headers_conflict_with_plain_headers_raises() -> None:
    entries = [
        owner(headers={"Authorization": "Bearer static"}),
        {
            "name": "srv",
            "secret_headers": {"Authorization": "svc.token"},
            "_profile": "contrib",
        },
    ]
    with pytest.raises(mcp_servers.MergeMcpServersError, match="Authorization"):
        mcp_servers._merge_mcp_servers(entries)


def test_merge_owner_declaring_header_in_both_places_raises() -> None:
    entries = [
        owner(
            headers={"Authorization": "Bearer static"},
            secret_headers={"Authorization": "svc.token"},
        )
    ]
    with pytest.raises(
        mcp_servers.MergeMcpServersError, match="both 'headers' and 'secret_headers'"
    ):
        mcp_servers._merge_mcp_servers(entries)


def test_merge_two_contributors_same_header_raises() -> None:
    entries = [
        owner(),
        {"name": "srv", "secret_headers": {"X-Key": "a.b"}, "_profile": "p1"},
        {"name": "srv", "secret_headers": {"X-Key": "c.d"}, "_profile": "p2"},
    ]
    with pytest.raises(mcp_servers.MergeMcpServersError, match="X-Key"):
        mcp_servers._merge_mcp_servers(entries)


def test_merge_secret_headers_only_entry_is_a_contribution() -> None:
    # An entry with only name/secret_headers/_profile must not be treated as
    # a standalone server (which would then fail for lacking command/url).
    entries = [
        owner(),
        {"name": "srv", "secret_headers": {"X-Key": "a.b"}, "_profile": "p1"},
    ]
    result = mcp_servers._merge_mcp_servers(entries)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# _resolve_secret_headers
# ---------------------------------------------------------------------------


def test_resolve_merges_plain_and_secret_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_decrypt(profile: str, key_path: str, dotfiles_dir: Path) -> str:
        calls.append((profile, key_path))
        return "s3cret"

    monkeypatch.setattr(mcp_servers, "decrypt_key", fake_decrypt)
    server = owner(
        headers={"X-Static": "v"},
        secret_headers={"Authorization": "svc.token"},
    )
    headers = mcp_servers._resolve_secret_headers(server, Path("/repo"))
    assert headers == {"X-Static": "v", "Authorization": "s3cret"}
    assert calls == [("own", "svc.token")]


def test_resolve_honors_profile_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mcp_servers,
        "decrypt_key",
        lambda profile, key_path, _dir: seen.append((profile, key_path)) or "v",
    )
    server = owner(secret_headers={"Authorization": "svc.token@other"})
    assert mcp_servers._resolve_secret_headers(server, Path("/repo")) is not None
    assert seen == [("other", "svc.token")]


def test_resolve_returns_none_when_any_secret_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_servers, "decrypt_key", lambda *a: None)
    server = owner(secret_headers={"Authorization": "svc.token"})
    assert mcp_servers._resolve_secret_headers(server, Path("/repo")) is None


# ---------------------------------------------------------------------------
# _normalize_config_files
# ---------------------------------------------------------------------------


def test_normalize_config_files_keeps_per_file_state() -> None:
    server = owner(
        config_files=[
            "~/plain.json",
            {"path": "~/target.json", "state": "present"},
            {"path": "~/pruned.json", "state": "absent", "optional": True},
        ]
    )
    normalized = mcp_servers._normalize_config_files(server, defaults=[])
    assert normalized == [
        {"path": "~/plain.json", "optional": False, "state": "present"},
        {"path": "~/target.json", "optional": False, "state": "present"},
        {"path": "~/pruned.json", "optional": True, "state": "absent"},
    ]


# ---------------------------------------------------------------------------
# _server_has_secrets
# ---------------------------------------------------------------------------


def test_url_server_with_secret_headers_counts_as_secret() -> None:
    assert mcp_servers._server_has_secrets(
        owner(secret_headers={"Authorization": "svc.token"})
    )


def test_url_server_without_secrets_is_not_secret() -> None:
    assert not mcp_servers._server_has_secrets(owner())

"""Tests for the resolve_github_signing_keys Ansible filter plugin.

The plugin resolves entries with a 'github_user' field into concrete SSH
signing key entries by fetching keys from the GitHub API. Entries with only
a 'key' field pass through unchanged.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# The filter plugin lives under ansible_plugins/filter/ which is not a package
# (no __init__.py), so we insert its parent onto sys.path and import by filename.
_PLUGIN_DIR = Path(__file__).parent.parent / "ansible_plugins" / "filter"
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import resolve_github_signing_keys as plugin_module  # noqa: E402
from resolve_github_signing_keys import FilterModule, _fetch_signing_keys  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear _fetch_signing_keys cache before every test to avoid cross-test
    contamination caused by lru_cache remembering previous results."""
    _fetch_signing_keys.cache_clear()
    yield
    _fetch_signing_keys.cache_clear()


@pytest.fixture
def filter_module():
    """Return a FilterModule instance."""
    return FilterModule()


def _make_urlopen_response(data: list[dict]) -> MagicMock:
    """Return a mock that behaves like the context manager returned by urlopen."""
    body = json.dumps(data).encode()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__ = MagicMock(return_value=False)
    cm.read = MagicMock(return_value=body)
    return cm


def _make_subprocess_result(
    returncode: int, stdout: str, stderr: str = ""
) -> MagicMock:
    """Return a mock subprocess.CompletedProcess-like object."""
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

KEY_ED25519 = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKey1"
KEY_RSA = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQExampleKey2"
KEY_EXTRA = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKey3"


# ---------------------------------------------------------------------------
# 1. Entries with only `key` pass through unchanged
# ---------------------------------------------------------------------------


class TestKeyOnlyEntries:
    """Entries that already have a 'key' field bypass all API calls."""

    def test_single_key_entry_passes_through(self, filter_module):
        entries = [{"email": "user@example.com", "key": KEY_ED25519}]

        result = filter_module.resolve_github_signing_keys(entries)

        assert result == entries

    def test_multiple_key_entries_pass_through(self, filter_module):
        entries = [
            {"email": "a@example.com", "key": KEY_ED25519},
            {"email": "b@example.com", "key": KEY_RSA},
        ]

        result = filter_module.resolve_github_signing_keys(entries)

        assert result == entries

    def test_empty_input_returns_empty(self, filter_module):
        result = filter_module.resolve_github_signing_keys([])

        assert result == []

    def test_no_github_user_entries_never_calls_which(self, filter_module):
        """When no github_user entries exist, shutil.which should never be called."""
        entries = [{"email": "user@example.com", "key": KEY_ED25519}]

        with patch("resolve_github_signing_keys.shutil.which") as mock_which:
            filter_module.resolve_github_signing_keys(entries)

        mock_which.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Entries with `github_user` are expanded via the GitHub API
# ---------------------------------------------------------------------------


class TestGithubUserExpansion:
    """Entries with github_user are replaced by one entry per signing key."""

    def test_single_github_user_single_key_expanded(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert result[0]["key"] == KEY_ED25519
        assert result[0]["email"] == "user@example.com"

    def test_github_user_with_no_keys_is_skipped(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "ghost"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, ""),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert result == []


# ---------------------------------------------------------------------------
# 3. A GitHub user with multiple signing keys produces multiple entries
# ---------------------------------------------------------------------------


class TestMultipleSigningKeys:
    """Each signing key for a github_user generates a separate output entry."""

    def test_two_keys_produce_two_entries(self, filter_module):
        gh_stdout = KEY_ED25519 + "\n" + KEY_RSA + "\n"
        entries = [{"email": "user@example.com", "github_user": "octocat"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, gh_stdout),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 2
        keys = {entry["key"] for entry in result}
        assert keys == {KEY_ED25519, KEY_RSA}
        # Every expanded entry preserves the original fields
        for entry in result:
            assert entry["email"] == "user@example.com"

    def test_three_keys_produce_three_entries(self, filter_module):
        gh_stdout = "\n".join([KEY_ED25519, KEY_RSA, KEY_EXTRA]) + "\n"
        entries = [{"email": "user@example.com", "github_user": "octocat"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, gh_stdout),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 3


# ---------------------------------------------------------------------------
# 4. Mixed entries (some `key`, some `github_user`) work correctly
# ---------------------------------------------------------------------------


class TestMixedEntries:
    """key-only entries and github_user entries can coexist in the same list."""

    def test_mixed_list_expands_only_github_user_entries(self, filter_module):
        entries = [
            {"email": "a@example.com", "key": KEY_RSA},
            {"email": "b@example.com", "github_user": "octocat"},
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 2
        # First entry is unchanged
        assert result[0] == {"email": "a@example.com", "key": KEY_RSA}
        # Second entry is expanded from github_user
        assert result[1] == {"email": "b@example.com", "key": KEY_ED25519}

    def test_order_is_preserved(self, filter_module):
        """key-only entries appear before github_user-expanded entries
        when that is the input order."""
        entries = [
            {"email": "first@example.com", "key": KEY_RSA},
            {"email": "second@example.com", "github_user": "octocat"},
            {"email": "third@example.com", "key": KEY_EXTRA},
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 3
        assert result[0]["email"] == "first@example.com"
        assert result[1]["email"] == "second@example.com"
        assert result[2]["email"] == "third@example.com"


# ---------------------------------------------------------------------------
# 5. `github_host` defaults to `github.com` when not specified
# ---------------------------------------------------------------------------


class TestGithubHostDefault:
    """When github_host is absent, the plugin passes 'github.com' to the API."""

    def test_default_host_is_github_com(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch("resolve_github_signing_keys.subprocess.run") as mock_run,
        ):
            mock_run.return_value = _make_subprocess_result(0, KEY_ED25519 + "\n")
            filter_module.resolve_github_signing_keys(entries)

        call_args = mock_run.call_args[0][0]  # positional argv list
        assert "--hostname" in call_args
        hostname_idx = call_args.index("--hostname")
        assert call_args[hostname_idx + 1] == "github.com"

    def test_explicit_github_host_is_used(self, filter_module):
        entries = [
            {
                "email": "user@example.com",
                "github_user": "octocat",
                "github_host": "github.mycompany.com",
            }
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch("resolve_github_signing_keys.subprocess.run") as mock_run,
        ):
            mock_run.return_value = _make_subprocess_result(0, KEY_ED25519 + "\n")
            filter_module.resolve_github_signing_keys(entries)

        call_args = mock_run.call_args[0][0]
        hostname_idx = call_args.index("--hostname")
        assert call_args[hostname_idx + 1] == "github.mycompany.com"


# ---------------------------------------------------------------------------
# 6. When `gh` CLI is not available, falls back to HTTPS API
# ---------------------------------------------------------------------------


class TestGhNotAvailable:
    """When shutil.which('gh') returns None, the HTTPS fallback is used directly."""

    def test_falls_back_to_https_when_gh_missing(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        api_response = [{"key": KEY_ED25519}, {"key": KEY_RSA}]

        with (
            patch("resolve_github_signing_keys.shutil.which", return_value=None),
            patch(
                "resolve_github_signing_keys.urlopen",
                return_value=_make_urlopen_response(api_response),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 2
        keys = {e["key"] for e in result}
        assert keys == {KEY_ED25519, KEY_RSA}

    def test_https_url_uses_api_github_com_for_default_host(self, filter_module):
        """For github.com the HTTPS fallback must use api.github.com, not
        github.com/api/v3."""
        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        api_response = [{"key": KEY_ED25519}]

        with (
            patch("resolve_github_signing_keys.shutil.which", return_value=None),
            patch("resolve_github_signing_keys.urlopen") as mock_urlopen,
        ):
            mock_urlopen.return_value = _make_urlopen_response(api_response)
            filter_module.resolve_github_signing_keys(entries)

        # The Request object is the first positional argument to urlopen
        request_obj = mock_urlopen.call_args[0][0]
        assert "api.github.com" in request_obj.full_url
        assert "/api/v3/" not in request_obj.full_url

    def test_https_url_uses_v3_path_for_enterprise_host(self, filter_module):
        """For non-github.com hosts the HTTPS fallback uses /{host}/api/v3/."""
        entries = [
            {
                "email": "user@example.com",
                "github_user": "octocat",
                "github_host": "github.mycompany.com",
            }
        ]
        api_response = [{"key": KEY_ED25519}]

        with (
            patch("resolve_github_signing_keys.shutil.which", return_value=None),
            patch("resolve_github_signing_keys.urlopen") as mock_urlopen,
        ):
            mock_urlopen.return_value = _make_urlopen_response(api_response)
            filter_module.resolve_github_signing_keys(entries)

        request_obj = mock_urlopen.call_args[0][0]
        assert "github.mycompany.com/api/v3/" in request_obj.full_url

    def test_subprocess_not_called_when_gh_missing(self, filter_module):
        """When gh is not on PATH, subprocess.run should never be invoked."""
        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        api_response = [{"key": KEY_ED25519}]

        with (
            patch("resolve_github_signing_keys.shutil.which", return_value=None),
            patch(
                "resolve_github_signing_keys.urlopen",
                return_value=_make_urlopen_response(api_response),
            ),
            patch("resolve_github_signing_keys.subprocess.run") as mock_run,
        ):
            filter_module.resolve_github_signing_keys(entries)

        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# 7. When `gh` CLI fails for a specific user, falls back to HTTPS
# ---------------------------------------------------------------------------


class TestGhFailureFallsBackToHttps:
    """A non-zero exit code from gh triggers the HTTPS fallback per-user."""

    def test_gh_nonzero_exit_triggers_https_fallback(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        api_response = [{"key": KEY_ED25519}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(1, "", "Not Found"),
            ),
            patch(
                "resolve_github_signing_keys.urlopen",
                return_value=_make_urlopen_response(api_response),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert result[0]["key"] == KEY_ED25519

    def test_gh_timeout_triggers_https_fallback(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        api_response = [{"key": KEY_ED25519}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                side_effect=plugin_module.subprocess.TimeoutExpired("gh", 15),
            ),
            patch(
                "resolve_github_signing_keys.urlopen",
                return_value=_make_urlopen_response(api_response),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert result[0]["key"] == KEY_ED25519

    def test_gh_oserror_triggers_https_fallback(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        api_response = [{"key": KEY_ED25519}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                side_effect=OSError("gh not executable"),
            ),
            patch(
                "resolve_github_signing_keys.urlopen",
                return_value=_make_urlopen_response(api_response),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert result[0]["key"] == KEY_ED25519


# ---------------------------------------------------------------------------
# 8. When both `gh` and HTTPS fail, entry is skipped with warning
# ---------------------------------------------------------------------------


class TestBothMethodsFail:
    """When all resolution strategies fail, the entry is silently dropped."""

    def test_entry_skipped_when_gh_and_https_both_fail(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "ghost"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(1, "", "error"),
            ),
            patch(
                "resolve_github_signing_keys.urlopen",
                side_effect=plugin_module.URLError("connection refused"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert result == []

    def test_other_entries_unaffected_when_one_user_fails(self, filter_module):
        entries = [
            {"email": "good@example.com", "key": KEY_RSA},
            {"email": "bad@example.com", "github_user": "ghost"},
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(1, "", "not found"),
            ),
            patch(
                "resolve_github_signing_keys.urlopen",
                side_effect=plugin_module.URLError("network error"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        # The key-only entry must survive; the failing github_user entry is dropped
        assert len(result) == 1
        assert result[0]["key"] == KEY_RSA


# ---------------------------------------------------------------------------
# 9. When user has no signing keys, entry is skipped
# ---------------------------------------------------------------------------


class TestNoSigningKeys:
    """A GitHub user with an empty signing-keys list causes the entry to be dropped."""

    def test_empty_key_list_from_gh_skips_entry(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "newuser"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, ""),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert result == []

    def test_empty_key_list_from_https_skips_entry(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "newuser"}]

        with (
            patch("resolve_github_signing_keys.shutil.which", return_value=None),
            patch(
                "resolve_github_signing_keys.urlopen",
                return_value=_make_urlopen_response([]),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert result == []

    def test_whitespace_only_gh_output_treated_as_no_keys(self, filter_module):
        """Lines containing only whitespace should not produce entries."""
        entries = [{"email": "user@example.com", "github_user": "newuser"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, "   \n  \n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert result == []


# ---------------------------------------------------------------------------
# 10. `profile` and `priority` fields are preserved through expansion
# ---------------------------------------------------------------------------


class TestFieldPreservation:
    """Arbitrary extra fields on an entry survive expansion."""

    def test_profile_field_preserved(self, filter_module):
        entries = [
            {
                "email": "user@example.com",
                "github_user": "octocat",
                "profile": "work",
            }
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert result[0]["profile"] == "work"

    def test_priority_field_preserved(self, filter_module):
        entries = [
            {
                "email": "user@example.com",
                "github_user": "octocat",
                "priority": 100,
            }
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert result[0]["priority"] == 100

    def test_all_extra_fields_preserved_across_multiple_expanded_keys(
        self, filter_module
    ):
        entries = [
            {
                "email": "user@example.com",
                "github_user": "octocat",
                "profile": "work",
                "priority": 42,
                "comment": "team lead",
            }
        ]
        gh_stdout = KEY_ED25519 + "\n" + KEY_RSA + "\n"

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, gh_stdout),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 2
        for entry in result:
            assert entry["email"] == "user@example.com"
            assert entry["profile"] == "work"
            assert entry["priority"] == 42
            assert entry["comment"] == "team lead"


# ---------------------------------------------------------------------------
# 11. `github_user` and `github_host` fields are stripped from output
# ---------------------------------------------------------------------------


class TestMetaFieldsStripped:
    """github_user and github_host must not appear in expanded output entries."""

    def test_github_user_stripped_from_output(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert "github_user" not in result[0]

    def test_github_host_stripped_from_output(self, filter_module):
        entries = [
            {
                "email": "user@example.com",
                "github_user": "octocat",
                "github_host": "github.mycompany.com",
            }
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 1
        assert "github_host" not in result[0]
        assert "github_user" not in result[0]

    def test_stripped_fields_absent_on_every_expanded_entry(self, filter_module):
        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        gh_stdout = KEY_ED25519 + "\n" + KEY_RSA + "\n"

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, gh_stdout),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 2
        for entry in result:
            assert "github_user" not in entry
            assert "github_host" not in entry


# ---------------------------------------------------------------------------
# 12. Caching: same (username, hostname) pair only fetches once
# ---------------------------------------------------------------------------


class TestCaching:
    """_fetch_signing_keys uses lru_cache; identical (user, host) pairs are
    resolved only once regardless of how many entries reference them."""

    def test_duplicate_users_fetch_only_once(self, filter_module):
        """Two entries with the same github_user trigger one API call, not two."""
        entries = [
            {"email": "a@example.com", "github_user": "octocat"},
            {"email": "b@example.com", "github_user": "octocat"},
        ]

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch("resolve_github_signing_keys.subprocess.run") as mock_run,
        ):
            mock_run.return_value = _make_subprocess_result(0, KEY_ED25519 + "\n")
            result = filter_module.resolve_github_signing_keys(entries)

        assert mock_run.call_count == 1
        # Both entries are expanded
        assert len(result) == 2
        assert all(e["key"] == KEY_ED25519 for e in result)

    def test_different_users_each_fetch_independently(self, filter_module):
        """Two entries with different github_user values trigger two API calls."""
        entries = [
            {"email": "a@example.com", "github_user": "octocat"},
            {"email": "b@example.com", "github_user": "torvalds"},
        ]

        def mock_run_side_effect(cmd, **_kwargs):
            # cmd is a list; the user appears inside the URL element, e.g.
            # "/users/octocat/ssh_signing_keys"
            url_element = next((s for s in cmd if s.startswith("/users/")), "")
            if "octocat" in url_element:
                return _make_subprocess_result(0, KEY_ED25519 + "\n")
            return _make_subprocess_result(0, KEY_RSA + "\n")

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                side_effect=mock_run_side_effect,
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 2
        keys = {e["key"] for e in result}
        assert keys == {KEY_ED25519, KEY_RSA}

    def test_same_user_different_hosts_fetch_independently(self, filter_module):
        """Same username on different hosts are treated as distinct cache keys."""
        entries = [
            {"email": "a@example.com", "github_user": "octocat"},
            {
                "email": "b@example.com",
                "github_user": "octocat",
                "github_host": "github.mycompany.com",
            },
        ]

        def mock_run_side_effect(cmd, **_kwargs):
            # cmd is a list; the hostname is the element after "--hostname"
            hostname_idx = cmd.index("--hostname") if "--hostname" in cmd else -1
            hostname = cmd[hostname_idx + 1] if hostname_idx >= 0 else ""
            if hostname == "github.mycompany.com":
                return _make_subprocess_result(0, KEY_RSA + "\n")
            return _make_subprocess_result(0, KEY_ED25519 + "\n")

        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                side_effect=mock_run_side_effect,
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert len(result) == 2
        assert result[0]["key"] == KEY_ED25519
        assert result[1]["key"] == KEY_RSA

    def test_cache_is_cleared_between_tests(self, filter_module):
        """Verify the autouse fixture actually isolates cache state between tests.

        This test poisons the cache via a direct call and then asserts the next
        resolve call uses a fresh fetch (not the poisoned cached value).
        """
        # Directly populate cache with a bad value
        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, "bad-key\n"),
            ),
        ):
            _fetch_signing_keys("octocat", "github.com", True)

        # Clear cache and re-resolve — should get the fresh value
        _fetch_signing_keys.cache_clear()

        entries = [{"email": "user@example.com", "github_user": "octocat"}]
        with (
            patch(
                "resolve_github_signing_keys.shutil.which", return_value="/usr/bin/gh"
            ),
            patch(
                "resolve_github_signing_keys.subprocess.run",
                return_value=_make_subprocess_result(0, KEY_ED25519 + "\n"),
            ),
        ):
            result = filter_module.resolve_github_signing_keys(entries)

        assert result[0]["key"] == KEY_ED25519


# ---------------------------------------------------------------------------
# FilterModule.filters() registration
# ---------------------------------------------------------------------------


class TestFilterModuleRegistration:
    """Verify the plugin registers itself correctly for Ansible."""

    def test_filters_returns_dict_with_correct_key(self, filter_module):
        filters = filter_module.filters()

        assert isinstance(filters, dict)
        assert "resolve_github_signing_keys" in filters

    def test_registered_callable_is_the_method(self, filter_module):
        filters = filter_module.filters()
        fn = filters["resolve_github_signing_keys"]

        assert callable(fn)
        # Bound methods create a new wrapper object on each access so identity
        # via `is` will always fail; compare the underlying function instead.
        assert fn.__func__ is filter_module.resolve_github_signing_keys.__func__

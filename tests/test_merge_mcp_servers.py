"""Tests for the merge_mcp_servers Ansible filter plugin.

The filter collapses cross-profile mcp_servers entries with the same `name:`
into a single record. Owners (entries with `command:` or `url:`) absorb
contributor entries, auto-suffixing cross-profile `secret_env` values with
`@<contributor>`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLUGIN_DIR = Path(__file__).parent.parent / "ansible_plugins" / "filter"
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from ansible.errors import AnsibleFilterError  # noqa: E402

from merge_mcp_servers import FilterModule  # noqa: E402


@pytest.fixture
def f():
    return FilterModule().filters()["merge_mcp_servers"]


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_single_owner_passes_through(f):
    entries = [
        {"name": "a", "_profile": "p1", "command": "a-srv", "secret_env": {"X": "s.x"}},
        {"name": "b", "_profile": "p2", "command": "b-srv", "secret_env": {"Y": "s.y"}},
    ]
    result = f(entries)
    assert len(result) == 2
    assert result[0]["secret_env"] == {"X": "s.x"}
    assert result[1]["secret_env"] == {"Y": "s.y"}


def test_contribution_from_other_profile_gets_suffix(f):
    entries = [
        {
            "name": "obsidian",
            "_profile": "productivity",
            "command": "obsidian-mcp-server",
        },
        {
            "name": "obsidian",
            "_profile": "adobe",
            "secret_env": {"ADOBE_KEY": "mcp_secrets.adobe.api_key"},
        },
    ]
    result = f(entries)
    assert len(result) == 1
    assert result[0]["secret_env"] == {"ADOBE_KEY": "mcp_secrets.adobe.api_key@adobe"}
    assert result[0]["command"] == "obsidian-mcp-server"
    assert result[0]["_profile"] == "productivity"


def test_home_profile_contribution_stays_bare(f):
    """A contributor entry from the owner's own profile gets no suffix."""
    entries = [
        {"name": "obs", "_profile": "productivity", "command": "x"},
        {
            "name": "obs",
            "_profile": "productivity",
            "secret_env": {"GARDEN": "mcp_secrets.garden.key"},
        },
    ]
    result = f(entries)
    assert result[0]["secret_env"] == {"GARDEN": "mcp_secrets.garden.key"}


def test_owner_existing_secret_env_preserved(f):
    entries = [
        {
            "name": "obs",
            "_profile": "productivity",
            "command": "x",
            "secret_env": {"GARDEN": "mcp_secrets.garden.key"},
        },
        {
            "name": "obs",
            "_profile": "adobe",
            "secret_env": {"ADOBE": "mcp_secrets.adobe.api_key"},
        },
    ]
    result = f(entries)
    assert result[0]["secret_env"] == {
        "GARDEN": "mcp_secrets.garden.key",
        "ADOBE": "mcp_secrets.adobe.api_key@adobe",
    }


def test_multiple_contributors_merge(f):
    entries = [
        {
            "name": "aggr",
            "_profile": "p0",
            "command": "x",
            "secret_env": {"OWN": "a.x"},
        },
        {"name": "aggr", "_profile": "p1", "secret_env": {"A": "a.y"}},
        {"name": "aggr", "_profile": "p2", "secret_env": {"B": "b.z"}},
    ]
    result = f(entries)
    assert len(result) == 1
    assert result[0]["secret_env"] == {
        "OWN": "a.x",
        "A": "a.y@p1",
        "B": "b.z@p2",
    }


def test_multiple_vars_in_one_contribution(f):
    entries = [
        {"name": "s", "_profile": "owner", "command": "x"},
        {"name": "s", "_profile": "contrib", "secret_env": {"A": "x.a", "B": "x.b"}},
    ]
    result = f(entries)
    assert result[0]["secret_env"] == {"A": "x.a@contrib", "B": "x.b@contrib"}


def test_url_based_owner(f):
    """An owner declared via `url:` instead of `command:` works the same."""
    entries = [
        {"name": "s", "_profile": "owner", "url": "https://x"},
        {"name": "s", "_profile": "contrib", "secret_env": {"K": "p"}},
    ]
    result = f(entries)
    assert result[0]["secret_env"] == {"K": "p@contrib"}


def test_env_contribution_not_suffixed(f):
    """Plain `env:` contributions are unioned verbatim — no @profile suffix."""
    entries = [
        {
            "name": "s",
            "_profile": "owner",
            "command": "x",
            "env": {"OWN_VAR": "own-val"},
        },
        {"name": "s", "_profile": "contrib", "env": {"NEW_VAR": "new-val"}},
    ]
    result = f(entries)
    assert result[0]["env"] == {"OWN_VAR": "own-val", "NEW_VAR": "new-val"}


def test_path_with_at_in_name_from_contributor(f):
    """Filter doesn't try to dedupe; resolver splits on the LAST `@`."""
    entries = [
        {"name": "s", "_profile": "o", "command": "x"},
        {"name": "s", "_profile": "c", "secret_env": {"X": "weird@path"}},
    ]
    result = f(entries)
    assert result[0]["secret_env"]["X"] == "weird@path@c"


def test_absent_entries_pass_through(f):
    """state: absent entries don't merge — they're removals, not contributions."""
    entries = [
        {"name": "obsidian", "_profile": "productivity", "command": "x"},
        {"name": "legacy", "_profile": "productivity", "state": "absent"},
        {"name": "obsidian", "_profile": "productivity", "state": "absent"},
    ]
    result = f(entries)
    assert len(result) == 3
    assert result[1]["state"] == "absent" and result[1]["name"] == "legacy"
    assert result[2]["state"] == "absent" and result[2]["name"] == "obsidian"


def test_no_command_but_has_secret_env_only_with_owner_elsewhere(f):
    """Owner-less secret_env entry (but owner exists in another entry) merges."""
    entries = [
        {"name": "s", "_profile": "a", "secret_env": {"K": "v"}},
        {"name": "s", "_profile": "o", "command": "x"},
    ]
    result = f(entries)
    assert len(result) == 1
    assert result[0]["secret_env"] == {"K": "v@a"}


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_duplicate_owners_raises(f):
    entries = [
        {"name": "dup", "_profile": "p1", "command": "a"},
        {"name": "dup", "_profile": "p2", "command": "b"},
    ]
    with pytest.raises(AnsibleFilterError) as exc:
        f(entries)
    msg = str(exc.value)
    assert "'p1'" in msg and "'p2'" in msg and "dup" in msg


def test_contribution_without_owner_raises(f):
    entries = [
        {"name": "ghost", "_profile": "c", "secret_env": {"X": "p"}},
    ]
    with pytest.raises(AnsibleFilterError) as exc:
        f(entries)
    msg = str(exc.value)
    assert "ghost" in msg and "c" in msg


def test_env_var_collision_between_contributors_raises(f):
    entries = [
        {"name": "s", "_profile": "o", "command": "x"},
        {"name": "s", "_profile": "p1", "secret_env": {"DUPE": "a"}},
        {"name": "s", "_profile": "p2", "secret_env": {"DUPE": "b"}},
    ]
    with pytest.raises(AnsibleFilterError) as exc:
        f(entries)
    msg = str(exc.value)
    assert "DUPE" in msg and "p1" in msg and "p2" in msg


def test_env_var_collision_with_owner_raises(f):
    entries = [
        {
            "name": "s",
            "_profile": "owner",
            "command": "x",
            "secret_env": {"VAR": "own.path"},
        },
        {"name": "s", "_profile": "contrib", "secret_env": {"VAR": "other.path"}},
    ]
    with pytest.raises(AnsibleFilterError) as exc:
        f(entries)
    msg = str(exc.value)
    assert "VAR" in msg and "owner" in msg and "contrib" in msg


def test_non_contribution_shape_passes_through(f):
    """Pruning entries (`name + config_files`) are not contributions."""
    entries = [
        {"name": "grafana", "_profile": "adobe", "command": "grafana-mcp"},
        {
            "name": "grafana-brand-service",
            "_profile": "adobe",
            "config_files": [{"path": "~/foo", "state": "absent"}],
        },
    ]
    result = f(entries)
    assert len(result) == 2
    assert result[1]["name"] == "grafana-brand-service"
    assert result[1]["config_files"] == [{"path": "~/foo", "state": "absent"}]


def test_name_only_entry_passes_through_not_orphan(f):
    """An entry with only `name` (no secret_env/env) is not a contribution."""
    entries = [
        {"name": "lonely", "_profile": "p"},
    ]
    result = f(entries)
    assert len(result) == 1
    assert result[0]["name"] == "lonely"


def test_contribution_non_dict_env_raises(f):
    entries = [
        {"name": "s", "_profile": "o", "command": "x"},
        {"name": "s", "_profile": "c", "secret_env": ["not", "a", "dict"]},
    ]
    with pytest.raises(AnsibleFilterError) as exc:
        f(entries)
    assert "non-mapping" in str(exc.value)


def test_contribution_non_string_value_raises(f):
    entries = [
        {"name": "s", "_profile": "o", "command": "x"},
        {"name": "s", "_profile": "c", "secret_env": {"X": 123}},
    ]
    with pytest.raises(AnsibleFilterError) as exc:
        f(entries)
    assert "X" in str(exc.value)


def test_entry_missing_name_raises(f):
    entries = [{"_profile": "p", "command": "x"}]
    with pytest.raises(AnsibleFilterError) as exc:
        f(entries)
    assert "name" in str(exc.value)


# ---------------------------------------------------------------------------
# Non-mutation guarantee
# ---------------------------------------------------------------------------


def test_inputs_not_mutated(f):
    entries = [
        {"name": "s", "_profile": "o", "command": "x", "secret_env": {"OWN": "own"}},
        {"name": "s", "_profile": "c", "secret_env": {"NEW": "p"}},
    ]
    snapshot = [{**e, "secret_env": dict(e.get("secret_env") or {})} for e in entries]
    f(entries)
    assert entries == snapshot


# ---------------------------------------------------------------------------
# Realistic end-to-end shape
# ---------------------------------------------------------------------------


def test_obsidian_multi_vault_scenario(f):
    """Productivity owns `obsidian`; adobe contributes its vault's key."""
    entries = [
        {
            "name": "obsidian",
            "_profile": "private-personal-productivity",
            "command": "obsidian-mcp-server",
            "secret_env": {
                "OBSIDIAN_API_KEY_GARDEN": "mcp_secrets.obsidian.digital_garden.api_key"
            },
        },
        {
            "name": "obsidian",
            "_profile": "private-adobe",
            "secret_env": {
                "OBSIDIAN_API_KEY_ADOBE": "mcp_secrets.obsidian_adobe.api_key"
            },
        },
    ]
    result = f(entries)
    assert len(result) == 1
    assert result[0]["secret_env"] == {
        "OBSIDIAN_API_KEY_GARDEN": "mcp_secrets.obsidian.digital_garden.api_key",
        "OBSIDIAN_API_KEY_ADOBE": "mcp_secrets.obsidian_adobe.api_key@private-adobe",
    }
    assert result[0]["command"] == "obsidian-mcp-server"

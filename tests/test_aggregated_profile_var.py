"""Tests for the aggregated_profile_var Ansible lookup plugin.

The lookup aggregates a variable across enabled profile hosts, sorting them by
``profile_priority`` (ascending) and applying one of several merge strategies
(list, dict, dict_recursive, first, last, any, all, none). It resolves the set
of profile hosts from ``ansible_limit`` (or ``dotfiles_enabled_profiles`` when
``all_profiles=True``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PLUGIN_DIR = Path(__file__).parent.parent / "ansible_plugins" / "lookup"
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from ansible.errors import AnsibleError  # noqa: E402

from aggregated_profile_var import LookupModule  # noqa: E402


def build_variables(profiles, *, limit=None, enabled=None):
    """Construct a ``variables`` dict shaped like Ansible passes to the lookup.

    ``profiles`` is an ordered mapping of ``profile_name -> {"priority": int,
    "vars": {...}}``. Each profile becomes a group with a single host named
    ``<profile>_host`` whose hostvars carry ``profile_priority`` plus the
    profile's variables.
    """
    groups = {"all": []}
    hostvars = {}
    for name, spec in profiles.items():
        host = f"{name}_host"
        groups.setdefault(name, []).append(host)
        groups["all"].append(host)
        hv = dict(spec.get("vars", {}))
        hv["profile_priority"] = spec["priority"]
        hostvars[host] = hv
    variables = {"hostvars": hostvars, "groups": groups}
    if limit is not None:
        variables["ansible_limit"] = limit
    if enabled is not None:
        variables["dotfiles_enabled_profiles"] = enabled
    return variables


@pytest.fixture
def lookup():
    return LookupModule()


def run(lookup, term, variables, **kwargs):
    """Run the lookup for a single term and return its aggregated value."""
    return lookup.run([term], variables=variables, **kwargs)[0]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_requires_variables(lookup):
    """run() without a variables mapping raises."""
    with pytest.raises(AnsibleError):
        lookup.run(["anything"], variables=None)


def test_invalid_merge_strategy_raises(lookup):
    variables = build_variables({"shell": {"priority": 100}}, limit="shell")
    with pytest.raises(AnsibleError) as exc:
        lookup.run(["x"], variables=variables, merge="bogus")
    assert "bogus" in str(exc.value)


# ---------------------------------------------------------------------------
# Host resolution and ordering
# ---------------------------------------------------------------------------


def test_hosts_term_returns_priority_sorted_hosts(lookup):
    """The `_hosts` term returns host names sorted by ascending priority."""
    variables = build_variables(
        {
            "dev": {"priority": 120},
            "shell": {"priority": 100},
            "agents": {"priority": 300},
        },
        limit="dev,shell,agents,localhost",
    )
    assert run(lookup, "_hosts", variables) == [
        "shell_host",
        "dev_host",
        "agents_host",
    ]


def test_localhost_is_excluded_from_limit(lookup):
    variables = build_variables({"shell": {"priority": 100}}, limit="shell,localhost")
    assert run(lookup, "_hosts", variables) == ["shell_host"]


def test_missing_priority_sorts_last(lookup):
    """Hosts without profile_priority default to 1000 and sort last."""
    variables = build_variables(
        {"shell": {"priority": 100}, "agents": {"priority": 300}},
        limit="shell,agents,localhost",
    )
    # Strip agents' priority so it falls back to the 1000 default.
    del variables["hostvars"]["agents_host"]["profile_priority"]
    assert run(lookup, "_hosts", variables) == ["shell_host", "agents_host"]


def test_no_limit_falls_back_to_all_group(lookup):
    """With no ansible_limit, hosts come from the `all` group."""
    variables = build_variables({"shell": {"priority": 100}, "dev": {"priority": 120}})
    assert run(lookup, "_hosts", variables) == ["shell_host", "dev_host"]


# ---------------------------------------------------------------------------
# list strategy (default)
# ---------------------------------------------------------------------------


def test_list_aggregation_nests_per_host(lookup):
    """List values are collected as per-host sub-lists (for lists_mergeby)."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"brew_packages": ["git", "fzf"]}},
            "dev": {"priority": 120, "vars": {"brew_packages": ["awscli"]}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "brew_packages", variables) == [["git", "fzf"], ["awscli"]]


def test_list_aggregation_skips_empty_and_missing(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"pkgs": ["a"]}},
            "dev": {"priority": 120, "vars": {"pkgs": []}},
            "agents": {"priority": 300},
        },
        limit="shell,dev,agents,localhost",
    )
    assert run(lookup, "pkgs", variables) == [["a"]]


def test_list_aggregation_collects_scalars_directly(lookup):
    """Scalar values are appended un-nested for path-like aggregations."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"root": "/a"}},
            "dev": {"priority": 120, "vars": {"root": "/b"}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "root", variables) == ["/a", "/b"]


# ---------------------------------------------------------------------------
# dict / dict_recursive strategies
# ---------------------------------------------------------------------------


def test_dict_higher_priority_overrides(lookup):
    """dict merge lets the highest-priority profile win on key collisions."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"cfg": {"a": 1, "b": 2}}},
            "dev": {"priority": 120, "vars": {"cfg": {"b": 99, "c": 3}}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "cfg", variables, merge="dict") == {"a": 1, "b": 99, "c": 3}


def test_dict_ignores_non_dict_values(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"cfg": {"a": 1}}},
            "dev": {"priority": 120, "vars": {"cfg": "not-a-dict"}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "cfg", variables, merge="dict") == {"a": 1}


def test_dict_recursive_deep_merges(lookup):
    variables = build_variables(
        {
            "shell": {
                "priority": 100,
                "vars": {"cfg": {"outer": {"a": 1, "b": 2}}},
            },
            "dev": {
                "priority": 120,
                "vars": {"cfg": {"outer": {"b": 99}, "extra": True}},
            },
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "cfg", variables, merge="dict_recursive") == {
        "outer": {"a": 1, "b": 99},
        "extra": True,
    }


def test_dict_recursive_does_not_mutate_source(lookup):
    """Deep merge must not mutate the nested dicts inside hostvars."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"cfg": {"outer": {"a": 1}}}},
            "dev": {"priority": 120, "vars": {"cfg": {"outer": {"b": 2}}}},
        },
        limit="shell,dev,localhost",
    )
    run(lookup, "cfg", variables, merge="dict_recursive")
    assert variables["hostvars"]["shell_host"]["cfg"] == {"outer": {"a": 1}}
    assert variables["hostvars"]["dev_host"]["cfg"] == {"outer": {"b": 2}}


# ---------------------------------------------------------------------------
# first / last strategies
# ---------------------------------------------------------------------------


def test_first_returns_lowest_priority_value(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"theme": "light"}},
            "dev": {"priority": 120, "vars": {"theme": "dark"}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "theme", variables, merge="first") == "light"


def test_first_skips_undefined_then_falls_back_to_default(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100},
            "dev": {"priority": 120, "vars": {"theme": "dark"}},
        },
        limit="shell,dev,localhost",
    )
    # shell has no theme, so first defined (by priority) is dev's.
    assert run(lookup, "theme", variables, merge="first", default="x") == "dark"


def test_first_returns_default_when_none_defined(lookup):
    variables = build_variables({"shell": {"priority": 100}}, limit="shell")
    assert run(lookup, "theme", variables, merge="first", default="fallback") == (
        "fallback"
    )


def test_last_returns_highest_priority_value(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"theme": "light"}},
            "dev": {"priority": 120, "vars": {"theme": "dark"}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "theme", variables, merge="last") == "dark"


def test_last_returns_default_when_none_defined(lookup):
    variables = build_variables({"shell": {"priority": 100}}, limit="shell")
    assert run(lookup, "theme", variables, merge="last", default="d") == "d"


# ---------------------------------------------------------------------------
# boolean strategies: any / all / none
# ---------------------------------------------------------------------------


def test_any_true_when_one_host_truthy(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"flag": False}},
            "dev": {"priority": 120, "vars": {"flag": True}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "flag", variables, merge="any") is True


def test_all_false_when_one_host_falsy(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"flag": True}},
            "dev": {"priority": 120, "vars": {"flag": False}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "flag", variables, merge="all") is False


def test_none_true_when_no_host_truthy(lookup):
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"flag": False}},
            "dev": {"priority": 120, "vars": {"flag": False}},
        },
        limit="shell,dev,localhost",
    )
    assert run(lookup, "flag", variables, merge="none") is True


def test_bool_uses_default_when_no_host_defines_var(lookup):
    variables = build_variables({"shell": {"priority": 100}}, limit="shell,localhost")
    assert run(lookup, "flag", variables, merge="any", default=True) is True
    assert run(lookup, "flag", variables, merge="any", default=False) is False


def test_bool_ignores_hosts_that_do_not_define_var(lookup):
    """Only hosts that define the var participate; undefined ones are skipped."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"flag": True}},
            "dev": {"priority": 120},
        },
        limit="shell,dev,localhost",
    )
    # dev does not define flag, so `all` sees only shell's True.
    assert run(lookup, "flag", variables, merge="all") is True


# ---------------------------------------------------------------------------
# all_profiles behavior
# ---------------------------------------------------------------------------


def test_all_profiles_reads_enabled_var_over_limit(lookup):
    """all_profiles=True aggregates the enabled set, ignoring the -p limit."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"pkgs": ["a"]}},
            "dev": {"priority": 120, "vars": {"pkgs": ["b"]}},
        },
        limit="shell,localhost",
        enabled="shell,dev,localhost",
    )
    # Limit alone would yield only shell; all_profiles widens to both.
    assert run(lookup, "pkgs", variables, all_profiles=True) == [["a"], ["b"]]


def test_all_profiles_falls_back_to_limit_without_enabled_var(lookup):
    """Without dotfiles_enabled_profiles, all_profiles behaves like the limit."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"pkgs": ["a"]}},
            "dev": {"priority": 120, "vars": {"pkgs": ["b"]}},
        },
        limit="shell,localhost",
    )
    assert run(lookup, "pkgs", variables, all_profiles=True) == [["a"]]


def test_default_all_profiles_false_uses_limit(lookup):
    """Default (all_profiles=False) narrows to the ansible_limit selection."""
    variables = build_variables(
        {
            "shell": {"priority": 100, "vars": {"pkgs": ["a"]}},
            "dev": {"priority": 120, "vars": {"pkgs": ["b"]}},
        },
        limit="shell,localhost",
        enabled="shell,dev,localhost",
    )
    assert run(lookup, "pkgs", variables) == [["a"]]


# ---------------------------------------------------------------------------
# Multiple terms
# ---------------------------------------------------------------------------


def test_multiple_terms_return_aligned_results(lookup):
    variables = build_variables(
        {
            "shell": {
                "priority": 100,
                "vars": {"brew_packages": ["git"], "theme": "light"},
            },
        },
        limit="shell,localhost",
    )
    results = lookup.run(["brew_packages", "theme"], variables=variables, merge="list")
    assert results[0] == [["git"]]
    # `theme` is a scalar, so the default list strategy collects it directly.
    assert results[1] == ["light"]

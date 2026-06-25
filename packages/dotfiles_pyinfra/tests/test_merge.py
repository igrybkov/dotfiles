"""Tests for the profile variable merge engine.

These verify the pure-Python reimplementation of the Ansible
``aggregated_profile_var`` lookup plugin and ``lists_mergeby`` filter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dotfiles_profile_discovery import ProfileInfo
from dotfiles_pyinfra.merge import (
    deep_merge,
    lists_mergeby,
    merge_var,
    sort_profiles,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_profile(
    name: str, priority: int, config: dict[str, Any] | None = None
) -> ProfileInfo:
    """Construct a ProfileInfo for testing.

    Only ``name``, ``priority`` and ``config`` carry meaningful values for
    the merge engine; the rest are filled with plausible placeholders.
    """
    return ProfileInfo(
        name=name,
        path=Path(f"/profiles/{name}"),
        relative_path=name,
        priority=priority,
        host_name=f"{name}-profile",
        connection="local",
        config=config or {},
    )


@pytest.fixture
def shell_profile() -> ProfileInfo:
    return make_profile(
        "shell",
        100,
        {
            "brew_packages": [{"name": "jq"}, {"name": "fd"}],
            "brew_upgrade_all": True,
            "gh_repos_default_dest": "~/src",
            "skill_folders": {"a": "~/.claude/skills"},
        },
    )


@pytest.fixture
def work_profile() -> ProfileInfo:
    return make_profile(
        "work",
        200,
        {
            "brew_packages": [{"name": "jq", "state": "absent"}, {"name": "kubectl"}],
            "brew_upgrade_all": False,
            "gh_repos_default_dest": "~/work",
            "skill_folders": {"b": "~/.cursor/skills"},
        },
    )


# ---------------------------------------------------------------------------
# sort_profiles
# ---------------------------------------------------------------------------


def test_sort_profiles_by_priority_ascending():
    p_late = make_profile("late", 300)
    p_early = make_profile("early", 50)
    p_mid = make_profile("mid", 120)
    ordered = sort_profiles([p_late, p_early, p_mid])
    assert [p.name for p in ordered] == ["early", "mid", "late"]


def test_sort_profiles_stable_tiebreak_by_name():
    a = make_profile("zebra", 100)
    b = make_profile("alpha", 100)
    ordered = sort_profiles([a, b])
    # Same priority → name breaks the tie alphabetically
    assert [p.name for p in ordered] == ["alpha", "zebra"]


def test_sort_profiles_empty():
    assert sort_profiles([]) == []


# ---------------------------------------------------------------------------
# merge_var — _profiles special term
# ---------------------------------------------------------------------------


def test_merge_var_profiles_special_term_returns_profile_list(
    shell_profile, work_profile
):
    profiles = [shell_profile, work_profile]
    result = merge_var(profiles, "_profiles")
    assert result == profiles
    # Returns a copy, not the same list object
    assert result is not profiles


# ---------------------------------------------------------------------------
# merge_var — list strategy (default)
# ---------------------------------------------------------------------------


def test_merge_var_list_returns_nested_sublists(shell_profile, work_profile):
    result = merge_var([shell_profile, work_profile], "brew_packages")
    assert result == [
        [{"name": "jq"}, {"name": "fd"}],
        [{"name": "jq", "state": "absent"}, {"name": "kubectl"}],
    ]


def test_merge_var_list_skips_empty_lists():
    p1 = make_profile("p1", 100, {"pkgs": []})
    p2 = make_profile("p2", 200, {"pkgs": [{"name": "x"}]})
    result = merge_var([p1, p2], "pkgs")
    assert result == [[{"name": "x"}]]


def test_merge_var_list_missing_key_yields_empty():
    p1 = make_profile("p1", 100, {})
    result = merge_var([p1], "brew_packages")
    assert result == []


def test_merge_var_list_scalar_appended_directly():
    # Path-like scalar variables are collected directly (not wrapped).
    p1 = make_profile("p1", 100, {"some_path": "/a"})
    p2 = make_profile("p2", 200, {"some_path": "/b"})
    result = merge_var([p1, p2], "some_path")
    assert result == ["/a", "/b"]


def test_merge_var_list_empty_profiles():
    assert merge_var([], "brew_packages") == []


# ---------------------------------------------------------------------------
# merge_var — dict / dict_recursive
# ---------------------------------------------------------------------------


def test_merge_var_dict_later_profile_overrides(shell_profile, work_profile):
    result = merge_var([shell_profile, work_profile], "skill_folders", "dict")
    assert result == {"a": "~/.claude/skills", "b": "~/.cursor/skills"}


def test_merge_var_dict_same_key_last_wins():
    p1 = make_profile("p1", 100, {"d": {"k": "first"}})
    p2 = make_profile("p2", 200, {"d": {"k": "second"}})
    result = merge_var([p1, p2], "d", "dict")
    assert result == {"k": "second"}


def test_merge_var_dict_shallow_does_not_deep_merge():
    p1 = make_profile("p1", 100, {"d": {"nested": {"a": 1}}})
    p2 = make_profile("p2", 200, {"d": {"nested": {"b": 2}}})
    result = merge_var([p1, p2], "d", "dict")
    # Shallow update replaces the whole nested dict
    assert result == {"nested": {"b": 2}}


def test_merge_var_dict_recursive_merges_nested():
    p1 = make_profile("p1", 100, {"d": {"nested": {"a": 1}}})
    p2 = make_profile("p2", 200, {"d": {"nested": {"b": 2}}})
    result = merge_var([p1, p2], "d", "dict_recursive")
    assert result == {"nested": {"a": 1, "b": 2}}


def test_merge_var_dict_ignores_non_dict_values():
    p1 = make_profile("p1", 100, {"d": "not-a-dict"})
    p2 = make_profile("p2", 200, {"d": {"k": "v"}})
    result = merge_var([p1, p2], "d", "dict")
    assert result == {"k": "v"}


# ---------------------------------------------------------------------------
# merge_var — first / last
# ---------------------------------------------------------------------------


def test_merge_var_first_returns_lowest_priority(shell_profile, work_profile):
    result = merge_var([shell_profile, work_profile], "gh_repos_default_dest", "first")
    assert result == "~/src"


def test_merge_var_last_returns_highest_priority(shell_profile, work_profile):
    result = merge_var([shell_profile, work_profile], "gh_repos_default_dest", "last")
    assert result == "~/work"


def test_merge_var_first_skips_undefined():
    p1 = make_profile("p1", 100, {})
    p2 = make_profile("p2", 200, {"v": "found"})
    assert merge_var([p1, p2], "v", "first") == "found"


def test_merge_var_first_default_when_absent():
    p1 = make_profile("p1", 100, {})
    assert merge_var([p1], "missing", "first", default="fallback") == "fallback"


def test_merge_var_last_default_when_absent():
    p1 = make_profile("p1", 100, {})
    assert merge_var([p1], "missing", "last", default="fallback") == "fallback"


# ---------------------------------------------------------------------------
# merge_var — bool strategies (any / all / none)
# ---------------------------------------------------------------------------


def test_merge_var_any_true_if_one_true(shell_profile, work_profile):
    # shell=True, work=False → any → True
    assert merge_var([shell_profile, work_profile], "brew_upgrade_all", "any") is True


def test_merge_var_all_false_if_one_false(shell_profile, work_profile):
    assert merge_var([shell_profile, work_profile], "brew_upgrade_all", "all") is False


def test_merge_var_none_false_if_any_true(shell_profile, work_profile):
    assert merge_var([shell_profile, work_profile], "brew_upgrade_all", "none") is False


def test_merge_var_bool_no_values_returns_default_true():
    p1 = make_profile("p1", 100, {})
    assert merge_var([p1], "missing", "any", default=True) is True


def test_merge_var_bool_no_values_returns_false_when_no_default():
    p1 = make_profile("p1", 100, {})
    assert merge_var([p1], "missing", "any") is False


def test_merge_var_none_true_when_all_false():
    p1 = make_profile("p1", 100, {"flag": False})
    p2 = make_profile("p2", 200, {"flag": False})
    assert merge_var([p1, p2], "flag", "none") is True


# ---------------------------------------------------------------------------
# merge_var — validation
# ---------------------------------------------------------------------------


def test_merge_var_invalid_strategy_raises():
    p1 = make_profile("p1", 100, {})
    with pytest.raises(ValueError, match="Invalid merge strategy"):
        merge_var([p1], "v", "bogus")


# ---------------------------------------------------------------------------
# lists_mergeby
# ---------------------------------------------------------------------------


def test_lists_mergeby_dedup_last_wins():
    result = lists_mergeby(
        [
            [{"name": "jq"}, {"name": "fd"}],
            [{"name": "jq", "state": "absent"}],
        ],
        "name",
    )
    assert result == [
        {"name": "jq", "state": "absent"},
        {"name": "fd"},
    ]


def test_lists_mergeby_merges_fields_not_just_replaces():
    # Later occurrence merges into the earlier dict (shallow), preserving
    # earlier keys that the override does not set.
    result = lists_mergeby(
        [
            [{"name": "jq", "tap": "core"}],
            [{"name": "jq", "state": "absent"}],
        ],
        "name",
    )
    assert result == [{"name": "jq", "tap": "core", "state": "absent"}]


def test_lists_mergeby_preserves_state_absent():
    # state:absent must pass through untouched (merge does not strip it).
    result = lists_mergeby([[{"name": "old", "state": "absent"}]], "name")
    assert result == [{"name": "old", "state": "absent"}]


def test_lists_mergeby_preserves_insertion_order():
    result = lists_mergeby(
        [[{"name": "a"}], [{"name": "b"}], [{"name": "c"}], [{"name": "a"}]],
        "name",
    )
    assert [item["name"] for item in result] == ["a", "b", "c"]


def test_lists_mergeby_skips_items_without_key():
    result = lists_mergeby([[{"name": "ok"}, {"no_key": "x"}]], "name")
    assert result == [{"name": "ok"}]


def test_lists_mergeby_empty():
    assert lists_mergeby([], "name") == []


def test_lists_mergeby_dedup_by_alternate_key():
    # mas packages dedup by "id", not "name"
    result = lists_mergeby(
        [
            [{"name": "Things", "id": 904280696}],
            [{"name": "Things 3", "id": 904280696}],
        ],
        "id",
    )
    assert result == [{"name": "Things 3", "id": 904280696}]


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


def test_deep_merge_nested():
    base = {"a": {"x": 1}, "b": 2}
    override = {"a": {"y": 3}, "c": 4}
    assert deep_merge(base, override) == {"a": {"x": 1, "y": 3}, "b": 2, "c": 4}


def test_deep_merge_override_replaces_scalar():
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}


def test_deep_merge_dict_replaces_non_dict():
    # When base value is not a dict, override (a dict) replaces it wholesale.
    assert deep_merge({"a": 1}, {"a": {"k": "v"}}) == {"a": {"k": "v"}}


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}}
    override = {"a": {"y": 2}}
    deep_merge(base, override)
    assert base == {"a": {"x": 1}}
    assert override == {"a": {"y": 2}}


def test_deep_merge_empty_override_returns_copy():
    base = {"a": 1}
    result = deep_merge(base, {})
    assert result == base
    assert result is not base


# ---------------------------------------------------------------------------
# End-to-end: merge_var(list) → lists_mergeby (the real pipeline)
# ---------------------------------------------------------------------------


def test_merge_then_dedup_pipeline(shell_profile, work_profile):
    nested = merge_var([shell_profile, work_profile], "brew_packages")
    result = lists_mergeby(nested, "name")
    # jq overridden to state:absent by the higher-priority work profile;
    # fd and kubectl preserved in order.
    assert result == [
        {"name": "jq", "state": "absent"},
        {"name": "fd"},
        {"name": "kubectl"},
    ]


def test_single_profile_merge(shell_profile):
    nested = merge_var([shell_profile], "brew_packages")
    result = lists_mergeby(nested, "name")
    assert result == [{"name": "jq"}, {"name": "fd"}]

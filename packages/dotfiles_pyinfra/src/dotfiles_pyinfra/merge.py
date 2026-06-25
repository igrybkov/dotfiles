"""Profile variable merge engine.

Replaces the Ansible ``aggregated_profile_var`` lookup plugin and
``community.general.lists_mergeby`` filter.

Key concepts:
  - Profiles are ordered by ``priority`` ascending (lower number = earlier).
  - ``merge_var(profiles, var_name, strategy)`` collects and merges ``var_name``
    from each profile's ``config`` dict.
  - ``lists_mergeby(lists, key)`` deduplicates a list-of-lists-of-dicts by a
    key field (last-wins), replacing ``community.general.lists_mergeby``.
  - Two merge contexts exist: ``merged_selected`` (the -p subset, for safe
    package installs) and ``merged_all`` (every enabled profile, for
    destructive config-file writes).
"""

from __future__ import annotations

from typing import Any

from dotfiles_profile_discovery import ProfileInfo


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def merge_var(
    profiles: list[ProfileInfo],
    var_name: str,
    strategy: str = "list",
    default: Any = None,
) -> Any:
    """Aggregate ``var_name`` from each profile's config dict.

    Parameters
    ----------
    profiles:
        Profiles sorted by priority ascending (as returned by
        ``sort_profiles`` / ``discover_profiles``).  Each profile's
        ``config`` attribute is a dict of the raw ``config.yml`` content.
    var_name:
        The key to read from each profile's config.  The special value
        ``"_profiles"`` returns the sorted list of :class:`ProfileInfo`
        objects instead of merging a config key.
    strategy:
        One of ``list``, ``dict``, ``dict_recursive``, ``first``,
        ``last``, ``any``, ``all``, ``none``.
    default:
        Fallback when no profile defines the variable (used by scalar
        strategies: ``first``, ``last``, boolean strategies).
    """
    if var_name == "_profiles":
        return list(profiles)

    _validate_strategy(strategy)

    if strategy == "first":
        return _aggregate_first(profiles, var_name, default)
    if strategy == "last":
        return _aggregate_last(profiles, var_name, default)
    if strategy in ("dict", "dict_recursive"):
        return _aggregate_dict(profiles, var_name, strategy)
    if strategy in ("any", "all", "none"):
        return _aggregate_bool(profiles, var_name, strategy, default)
    # default: list
    return _aggregate_list(profiles, var_name)


def lists_mergeby(nested: list[list[dict[str, Any]]], key: str) -> list[dict[str, Any]]:
    """Flatten nested per-profile lists and deduplicate by ``key`` (last-wins).

    Replaces ``community.general.lists_mergeby``.

    Example::

        lists_mergeby([[{"name": "jq"}, {"name": "fd"}],
                       [{"name": "jq", "state": "absent"}]],
                      "name")
        # → [{"name": "jq", "state": "absent"}, {"name": "fd"}]
    """
    merged: dict[Any, dict[str, Any]] = {}
    for sublist in nested:
        for item in sublist:
            k = item.get(key)
            if k is None:
                continue
            if k in merged:
                merged[k] = {**merged[k], **item}
            else:
                merged[k] = dict(item)
    return list(merged.values())


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base``.

    Mirrors Ansible's ``combine(recursive=true)`` and the ``_deep_merge``
    method in the old Ansible lookup plugin.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def sort_profiles(profiles: list[ProfileInfo]) -> list[ProfileInfo]:
    """Sort profiles by priority ascending (lower priority number = earlier)."""
    return sorted(profiles, key=lambda p: (p.priority, p.name))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_VALID_STRATEGIES = frozenset(
    {"list", "dict", "dict_recursive", "first", "last", "any", "all", "none"}
)


def _validate_strategy(strategy: str) -> None:
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(
            f"Invalid merge strategy {strategy!r}. "
            f"Valid options: {', '.join(sorted(_VALID_STRATEGIES))}"
        )


def _aggregate_list(profiles: list[ProfileInfo], var_name: str) -> list[Any]:
    """Return per-profile sub-lists (nested).

    The result is suitable for passing to :func:`lists_mergeby` for dedup.
    Scalar values are appended directly.
    """
    result = []
    for profile in profiles:
        value = profile.config.get(var_name, [])
        if isinstance(value, list):
            if value:
                result.append(value)
        elif value:
            result.append(value)
    return result


def _aggregate_dict(
    profiles: list[ProfileInfo], var_name: str, strategy: str
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for profile in profiles:
        value = profile.config.get(var_name, {})
        if isinstance(value, dict):
            if strategy == "dict_recursive":
                result = deep_merge(result, value)
            else:
                result.update(value)
    return result


def _aggregate_first(profiles: list[ProfileInfo], var_name: str, default: Any) -> Any:
    for profile in profiles:
        value = profile.config.get(var_name)
        if value is not None:
            return value
    return default


def _aggregate_last(profiles: list[ProfileInfo], var_name: str, default: Any) -> Any:
    for profile in reversed(profiles):
        value = profile.config.get(var_name)
        if value is not None:
            return value
    return default


def _aggregate_bool(
    profiles: list[ProfileInfo], var_name: str, strategy: str, default: Any
) -> bool:
    values = []
    for profile in profiles:
        if var_name in profile.config:
            values.append(bool(profile.config[var_name]))
    if not values:
        return bool(default) if default is not None else False
    if strategy == "any":
        return any(values)
    if strategy == "all":
        return all(values)
    # none
    return not any(values)

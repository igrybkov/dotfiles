"""osx_defaults idempotent operation — wraps ``defaults read/write``.

Idempotency is decided at pyinfra *build* time: we read the current value with
``defaults read`` and only emit a ``defaults write`` (or ``delete``) operation
when the on-disk value differs from what we want. ``defaults read`` works even
when the owning app is not running, so doing this at build time is safe.

``set_default`` returns ``True`` when it emits a mutating operation and ``False``
when the setting is already in the desired state. Callers use this to gate
follow-up actions (e.g. restarting Dock/Finder only when something changed).
"""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

from pyinfra.operations import server

TYPE_MAP = {
    "bool": "-bool",
    "boolean": "-bool",
    "integer": "-int",
    "int": "-int",
    "float": "-float",
    "string": "-string",
    "array": "-array",
    "dict": "-dict",
}


def _current_value(domain: str, key: str) -> str | None:
    """Read current defaults value. Returns string representation or None if missing."""
    cmd = ["defaults", "read", domain, key]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _normalize_for_comparison(value: Any, type_: str) -> str:
    """Normalize a desired value into the string ``defaults read`` would emit."""
    if type_ in ("bool", "boolean"):
        return "1" if value else "0"
    if type_ in ("integer", "int", "float"):
        # `defaults read` prints whole numbers without a decimal point, e.g.
        # `defaults write ... -float 3` reads back as "3". Coerce numeric
        # values (including 3.0) to an int string when they are whole, so a
        # float-typed setting stays idempotent instead of rewriting each run.
        try:
            num = float(value)
        except TypeError, ValueError:
            return str(value)
        if num.is_integer():
            return str(int(num))
        return str(num)
    return str(value)


def set_default(
    name: str,
    domain: str,
    key: str,
    type_: str,
    value: Any,
    state: str = "present",
) -> bool:
    """Emit a ``defaults write`` operation, idempotent by checking current value.

    Args:
        name: Human-readable operation name
        domain: defaults domain (e.g. 'com.apple.dock', 'NSGlobalDomain')
        key: defaults key
        type_: one of 'bool'/'boolean'/'integer'/'int'/'float'/'string'
        value: desired value
        state: 'present' (write) or 'absent' (delete)

    Returns:
        ``True`` if a mutating operation was emitted, ``False`` if the setting
        was already in the desired state (no operation emitted).
    """
    if state == "absent":
        current = _current_value(domain, key)
        if current is None:
            return False  # already absent
        server.shell(
            name=name,
            commands=[f"defaults delete {shlex.quote(domain)} {shlex.quote(key)}"],
        )
        return True

    # state == "present"
    current = _current_value(domain, key)
    expected = _normalize_for_comparison(value, type_)
    if current == expected:
        return False  # already at desired value

    type_flag = TYPE_MAP.get(type_, f"-{type_}")
    # Quote value appropriately
    if type_ in ("bool", "boolean"):
        val_str = "true" if value else "false"
    else:
        val_str = shlex.quote(str(value))

    cmd = (
        f"defaults write {shlex.quote(domain)} {shlex.quote(key)} {type_flag} {val_str}"
    )
    server.shell(name=name, commands=[cmd])
    return True

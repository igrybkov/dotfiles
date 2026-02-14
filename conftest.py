"""Root pytest configuration for dotfiles tests."""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Dynamic profile package discovery
# Adds profile/*/packages/*/src directories to sys.path so tests can import
# profile-local packages without adding them as workspace members
# ---------------------------------------------------------------------------
_root = Path(__file__).parent
for _profile_dir in (_root / "profiles").iterdir():
    if not _profile_dir.is_dir():
        continue
    _packages_dir = _profile_dir / "packages"
    if not _packages_dir.exists():
        continue
    for _pkg_dir in _packages_dir.iterdir():
        _src_dir = _pkg_dir / "src"
        if _src_dir.is_dir() and str(_src_dir) not in sys.path:
            sys.path.insert(0, str(_src_dir))

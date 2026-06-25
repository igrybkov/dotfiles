"""Dotfiles symlink deploy — home, ~/.config, ~/.local/bin, skills, agents, copies.

Mirrors the logic of ``roles/dotfiles/tasks/main.yml`` (and its included task
files ``symlink_recursive.yml``, ``cleanup_recursive.yml``, ``copy_dotfiles.yml``).

All profile source directories are aggregated across every (enabled) profile and
passed to ``symlink-dotfiles`` in a single batch per target, matching the
aggregation pattern of the Ansible role.

Ordering (same as the Ansible role):
  1. Ensure ~/.config and ~/.local/bin exist
  2. Clean dead symlinks: ~ (depth 1), nested dotfiles dirs, ~/.config,
     ~/.local/bin, each skill folder, each agent folder
  3. Symlink dotfiles dirs → ~ with prefix "." (excluding the "config" subdir)
  4. Symlink config dirs → ~/.config with prefix ""
  5. Symlink bin dirs → ~/.local/bin with prefix ""
  6. Symlink skills dirs → each skill folder with prefix ""
  7. Symlink agents dirs → each agent folder with prefix ""
  8. Copy (not symlink) dotfiles-copy dirs → ~/

Notes on idempotency / change reporting:
  ``symlink-dotfiles`` is idempotent, so the CLI is run unconditionally via
  ``server.shell``. Unlike the Ansible role (which sets ``changed_when`` from the
  parsed JSON ``changed`` flag), pyinfra's ``server.shell`` does not support a
  post-hoc change callback. Running the idempotent CLI directly is the documented
  simplest-correct approach: it is a no-op on subsequent runs.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from pyinfra.operations import files, server

# Name of the marker file that opts a directory into directory-level symlinking
# (matches ``dotfiles_directory_marker`` in roles/dotfiles/defaults/main.yml).
DIRECTORY_MARKER = ".symlink-as-directory"

# Depth fallback for recursive dead-symlink cleanup when a profile does not
# override ``dotfiles_cleanup_depth``. The spec uses 10; the role default is 3.
DEFAULT_CLEANUP_DEPTH = 10

# Path to the symlink-dotfiles CLI installed into the project venv.
SYMLINK_CLI = ".venv/bin/symlink-dotfiles"


def deploy(profiles: list, dotfiles_dir: Path) -> None:
    """Deploy all dotfile symlinks and copies for the given profiles.

    Args:
        profiles: ``ProfileInfo`` objects, sorted by priority, already filtered
            to the enabled set.
        dotfiles_dir: Root of the dotfiles repository.
    """
    home = Path.home()
    config_dir = home / ".config"
    bin_target = home / ".local" / "bin"

    cli = str(dotfiles_dir / SYMLINK_CLI)

    # --- Aggregate source directories across all profiles -------------------
    # Later profiles (higher priority value) override earlier ones; we preserve
    # the incoming order and only drop sources that do not exist on disk.

    # Base "dotfiles" dirs plus any per-profile additional dotfiles dirs. These
    # feed both the home batch (prefix ".") and the ~/.config batch (each with
    # "/config" appended), exactly as the role does.
    dotfiles_roots: list[Path] = []
    for profile in profiles:
        dotfiles_roots.append(profile.path / "files" / "dotfiles")
        for extra in profile.config.get("additional_dotfiles_dirs", []) or []:
            dotfiles_roots.append(Path(extra).expanduser())

    home_sources = [p for p in dotfiles_roots if p.exists()]
    config_sources = [sub for p in dotfiles_roots if (sub := p / "config").exists()]

    bin_sources = [
        b for profile in profiles if (b := profile.path / "files" / "bin").exists()
    ]
    skill_sources = [
        s for profile in profiles if (s := profile.path / "files" / "skills").exists()
    ]
    agent_sources = [
        a for profile in profiles if (a := profile.path / "files" / "agents").exists()
    ]

    # Destination folders for skills/agents, aggregated and de-duplicated across
    # all profiles (dict.fromkeys preserves first-seen / priority order).
    skill_folders = _dedupe_folders(profiles, "skill_folders")
    agent_folders = _dedupe_folders(profiles, "agent_folders")

    # Deepest cleanup depth requested by any profile (the role applies a single
    # depth per cleanup; we take the max so no profile is under-cleaned).
    cleanup_depth = max(
        (
            int(p.config.get("dotfiles_cleanup_depth", DEFAULT_CLEANUP_DEPTH))
            for p in profiles
        ),
        default=DEFAULT_CLEANUP_DEPTH,
    )

    # --- 1. Ensure base target directories exist ----------------------------
    files.directory(
        name="Ensure ~/.config exists",
        path=str(config_dir),
        present=True,
        mode="755",
    )
    files.directory(
        name="Ensure ~/.local/bin exists",
        path=str(bin_target),
        present=True,
        mode="755",
    )
    for folder in skill_folders:
        files.directory(
            name=f"Ensure skill folder {folder} exists",
            path=str(folder),
            present=True,
            mode="755",
        )
    for folder in agent_folders:
        files.directory(
            name=f"Ensure agent folder {folder} exists",
            path=str(folder),
            present=True,
            mode="755",
        )

    # --- 2. Clean dead symlinks ---------------------------------------------
    # Home is cleaned at depth 1; managed subtrees at the configured depth.
    _cleanup(home, depth=1)

    # Nested dotfiles dirs (e.g. ~/.claude, ~/.vim): top-level dirs found under
    # any profile's files/dotfiles, excluding "config" (handled separately).
    for nested in _nested_dotfiles_names(profiles):
        _cleanup(home / f".{nested}", depth=cleanup_depth)

    _cleanup(config_dir, depth=cleanup_depth)
    _cleanup(bin_target, depth=cleanup_depth)
    for folder in skill_folders:
        _cleanup(folder, depth=cleanup_depth)
    for folder in agent_folders:
        _cleanup(folder, depth=cleanup_depth)

    # --- 3. Symlink dotfiles → ~ (prefix ".", excluding "config") -----------
    if home_sources:
        _symlink(
            name="Symlink dotfiles to home",
            cli=cli,
            sources=home_sources,
            target=home,
            prefix=".",
            excludes=["config"],
        )

    # --- 4. Symlink config → ~/.config (prefix "") --------------------------
    if config_sources:
        _symlink(
            name="Symlink config dotfiles to ~/.config",
            cli=cli,
            sources=config_sources,
            target=config_dir,
            prefix="",
        )

    # --- 5. Symlink bin → ~/.local/bin (prefix "") --------------------------
    if bin_sources:
        _symlink(
            name="Symlink bin scripts to ~/.local/bin",
            cli=cli,
            sources=bin_sources,
            target=bin_target,
            prefix="",
        )

    # --- 6. Symlink skills → each skill folder (prefix "") ------------------
    if skill_sources:
        for folder in skill_folders:
            _symlink(
                name=f"Symlink skills to {folder}",
                cli=cli,
                sources=skill_sources,
                target=folder,
                prefix="",
            )

    # --- 7. Symlink agents → each agent folder (prefix "") ------------------
    if agent_sources:
        for folder in agent_folders:
            _symlink(
                name=f"Symlink agents to {folder}",
                cli=cli,
                sources=agent_sources,
                target=folder,
                prefix="",
            )

    # --- 8. Copy (not symlink) dotfiles-copy dirs → ~/ ----------------------
    for profile in profiles:
        copy_dir = profile.path / "files" / "dotfiles-copy"
        if copy_dir.is_dir():
            _copy_dir(copy_dir, home)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedupe_folders(profiles: list, key: str) -> list[Path]:
    """Aggregate a folder-list config key across all profiles, de-duplicated.

    Accepts both the dict shape documented in the spec (keys are the
    destination dirs) and a plain list shape. ``~`` is expanded so the resulting
    paths are absolute.
    """
    collected: list[str] = []
    for profile in profiles:
        value = profile.config.get(key, {}) or {}
        # dict → its keys are the destination dirs; list → the entries are dirs.
        collected.extend(value.keys() if isinstance(value, dict) else value)
    # Preserve first-seen (priority) order while removing duplicates.
    return [Path(f).expanduser() for f in dict.fromkeys(collected)]


def _nested_dotfiles_names(profiles: list) -> list[str]:
    """Top-level directory names under each profile's files/dotfiles.

    Excludes "config" (which targets ~/.config, not ~/.{name}). Names are
    de-duplicated and returned in sorted order to match the role's ``sort -u``.
    """
    names: set[str] = set()
    for profile in profiles:
        root = profile.path / "files" / "dotfiles"
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and child.name != "config":
                names.add(child.name)
    return sorted(names)


def _symlink(
    *,
    name: str,
    cli: str,
    sources: list[Path],
    target: Path,
    prefix: str,
    excludes: list[str] | None = None,
) -> None:
    """Run the symlink-dotfiles CLI for a single target batch.

    The CLI is idempotent, so it is run unconditionally. The command string is
    assembled with ``shlex.quote`` for every path so spaces and shell
    metacharacters are safe.
    """
    parts = [shlex.quote(cli)]
    for src in sources:
        parts += ["--source", shlex.quote(str(src))]
    parts += ["--target", shlex.quote(str(target))]
    parts += ["--prefix", shlex.quote(prefix)]
    for exclude in excludes or []:
        parts += ["--exclude", shlex.quote(exclude)]
    parts += ["--marker", shlex.quote(DIRECTORY_MARKER)]
    parts.append("--json")

    server.shell(name=name, commands=[" ".join(parts)])


def _cleanup(directory: Path, *, depth: int) -> None:
    """Delete dead (broken) symlinks under ``directory`` up to ``depth``.

    Guarded so a missing directory or a ``find`` that lacks ``-xtype`` (stock
    macOS BSD find) is a silent no-op rather than a failure.
    """
    quoted = shlex.quote(str(directory))
    server.shell(
        name=f"Clean dead symlinks in {directory}",
        commands=[
            f"find {quoted} -maxdepth {int(depth)} -xtype l -delete 2>/dev/null || true"
        ],
    )


def _copy_dir(copy_dir: Path, home: Path) -> None:
    """Copy each top-level item in ``copy_dir`` to ``~/.{basename}``.

    Mirrors ``copy_dotfiles.yml``: each entry is copied (not symlinked) with a
    leading dot prefix, and existing files are not clobbered. The guard
    ``[[ -e dest ]] || cp -R src dest`` avoids the macOS BSD ``cp -n`` quirk
    where a skipped copy exits 1 (unlike GNU cp which exits 0). The source
    directory is enumerated at build time, which is safe because deploy code
    runs before any operation executes.
    """
    for item in sorted(copy_dir.iterdir()):
        dest = home / f".{item.name}"
        src = shlex.quote(str(item))
        dst = shlex.quote(str(dest))
        server.shell(
            name=f"Copy {item.name} to ~/{dest.relative_to(home)}",
            commands=[f"[[ -e {dst} ]] || cp -R {src} {dst}"],
        )

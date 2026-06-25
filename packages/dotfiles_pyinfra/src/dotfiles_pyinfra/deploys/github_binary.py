"""Install or update binaries from GitHub releases.

Mirrors the logic of ``roles/github_binary/tasks/`` (``main.yml`` +
``install_one.yml``).

Version resolution happens at build time: for each binary we query the latest
release tag with ``gh`` and compare it against a sidecar version file
(``<install_dir>/.<name>.version``). If they match, no operations are emitted
for that binary. Otherwise we (re)download/extract and record the new tag.

Asset selection is platform-aware, matching the precedence in the Ansible role:
explicit ``asset`` wins outright; otherwise darwin arm64 / x86_64 / generic
darwin / linux variants are chosen based on the build host.
"""

from __future__ import annotations

import io
import platform
import shlex
import subprocess
from pathlib import Path
from typing import Any

from pyinfra import logger
from pyinfra.operations import files, server


def deploy(merged: dict[str, Any]) -> None:
    """Install/update every binary declared in ``github_binaries``."""
    binaries: list[dict[str, Any]] = merged.get("github_binaries", [])
    install_dir = Path(
        merged.get("github_binary_install_dir", "~/.local/bin")
    ).expanduser()

    is_darwin = platform.system() == "Darwin"
    is_arm64 = platform.machine() == "arm64"

    for binary in binaries:
        _install_one(binary, install_dir, is_darwin=is_darwin, is_arm64=is_arm64)


def _install_one(
    binary: dict[str, Any],
    install_dir: Path,
    *,
    is_darwin: bool,
    is_arm64: bool,
) -> None:
    name = binary["name"]
    repo = binary["repo"]

    asset = _resolve_asset(binary, is_darwin=is_darwin, is_arm64=is_arm64)
    if asset is None:
        logger.warning(
            f"No matching asset for {name} ({repo}) on this platform — skipping."
        )
        return

    latest_tag = _latest_release_tag(repo)
    if latest_tag is None:
        return

    version_file = install_dir / f".{name}.version"
    installed_tag = version_file.read_text().strip() if version_file.exists() else ""

    if installed_tag == latest_tag:
        # Up to date — emit no operations.
        return

    files.directory(
        name=f"Ensure install dir exists for {name}",
        path=str(install_dir),
        mode="755",
    )

    binary_type = binary.get("type", "binary")
    target = install_dir / name

    if binary_type == "tarball":
        _download_tarball(name, repo, asset, latest_tag, target)
    else:
        _download_binary(name, repo, asset, latest_tag, install_dir, target)

    files.put(
        name=f"Record {name} version",
        src=io.BytesIO(latest_tag.encode()),
        dest=str(version_file),
        mode="644",
    )


def _resolve_asset(
    binary: dict[str, Any],
    *,
    is_darwin: bool,
    is_arm64: bool,
) -> str | None:
    """Pick the asset name for this platform, or None if nothing matches."""
    if is_darwin and is_arm64 and "asset_darwin_arm64" in binary:
        return binary["asset_darwin_arm64"]
    if is_darwin and "asset_darwin_x86_64" in binary:
        return binary["asset_darwin_x86_64"]
    if is_darwin and "asset_darwin" in binary:
        return binary["asset_darwin"]
    if not is_darwin and "asset_linux" in binary:
        return binary["asset_linux"]
    if "asset" in binary:
        return binary["asset"]
    return None


def _latest_release_tag(repo: str) -> str | None:
    """Query the latest release tag for ``repo`` via the gh CLI."""
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            "--repo",
            repo,
            "--json",
            "tagName",
            "-q",
            ".tagName",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        logger.warning(f"Cannot get latest release for {repo}: {result.stderr.strip()}")
        return None
    return result.stdout.strip()


def _download_binary(
    name: str,
    repo: str,
    asset: str,
    tag: str,
    install_dir: Path,
    target: Path,
) -> None:
    server.shell(
        name=f"Download {name} {tag}",
        commands=[
            f"gh release download {shlex.quote(tag)}"
            f" --repo {shlex.quote(repo)}"
            f" --pattern {shlex.quote(asset)}"
            f" --dir {shlex.quote(str(install_dir))}"
            f" --clobber",
            f"chmod 755 {shlex.quote(str(target))}",
        ],
    )


def _download_tarball(
    name: str,
    repo: str,
    asset: str,
    tag: str,
    target: Path,
) -> None:
    server.shell(
        name=f"Download and extract {name} {tag}",
        commands=[
            "TMPDIR=$(mktemp -d)",
            f"gh release download {shlex.quote(tag)}"
            f" --repo {shlex.quote(repo)}"
            f" --pattern {shlex.quote(asset)}"
            f' --dir "$TMPDIR" --clobber',
            f'tar xzf "$TMPDIR/{asset}" -C "$TMPDIR"',
            f'mv "$TMPDIR/{name}" {shlex.quote(str(target))}',
            f"chmod 755 {shlex.quote(str(target))}",
            'rm -rf "$TMPDIR"',
        ],
    )

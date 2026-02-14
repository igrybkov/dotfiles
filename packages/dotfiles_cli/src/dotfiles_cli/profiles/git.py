"""Git operations for profile repositories."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import click

from ..constants import DOTFILES_DIR


async def _run_git_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command asynchronously."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return subprocess.CompletedProcess(
        args=args,
        returncode=proc.returncode,
        stdout=stdout.decode(),
        stderr=stderr.decode(),
    )


async def _check_repo_status(name: str, repo_path: Path) -> tuple[str, bool, bool]:
    """Check a single repo for uncommitted changes and unpushed commits.

    Returns:
        Tuple of (repo_name, has_uncommitted, has_unpushed)
    """
    # Run both checks concurrently
    status_task = _run_git_command(["git", "status", "--porcelain"], repo_path)
    tracking_task = _run_git_command(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo_path
    )

    status_result, tracking_result = await asyncio.gather(status_task, tracking_task)

    has_uncommitted = bool(status_result.stdout.strip())

    # Check for unpushed commits only if tracking branch exists
    has_unpushed = False
    if tracking_result.returncode == 0:
        ahead_result = await _run_git_command(
            ["git", "rev-list", "--count", "@{u}..HEAD"], repo_path
        )
        has_unpushed = (
            ahead_result.returncode == 0 and int(ahead_result.stdout.strip() or "0") > 0
        )

    return name, has_uncommitted, has_unpushed


def get_repos_with_unpushed_changes() -> tuple[list[str], list[str]]:
    """Get all repos (main + profiles) with uncommitted or unpushed changes.

    Runs all git checks in parallel for better performance.

    Returns:
        Tuple of (uncommitted_repos, unpushed_repos) where each is a list of display names
    """

    async def check_all_repos() -> tuple[list[str], list[str]]:
        # Build list of repos to check
        repos_to_check = [("dotfiles", Path(DOTFILES_DIR))]
        for repo in get_profile_repos():
            repos_to_check.append((f"profiles/{repo.name}", repo))

        # Run all checks in parallel
        results = await asyncio.gather(
            *[_check_repo_status(name, path) for name, path in repos_to_check]
        )

        uncommitted = []
        unpushed = []
        for name, has_uncommitted, has_unpushed in results:
            if has_uncommitted:
                uncommitted.append(name)
            if has_unpushed:
                unpushed.append(name)

        return uncommitted, unpushed

    return asyncio.run(check_all_repos())


def get_profile_repos() -> list[Path]:
    """Get all git repositories in profiles/ directory.

    Searches for .git directories at levels 1 and 2:
    - profiles/{repo}/.git (for 1-2 level profiles)
    - profiles/{dir}/{repo}/.git (for 3-level profiles like private/myrepo/work)

    Returns:
        List of paths to directories that are git repositories
    """
    repos = []
    profiles_dir = Path(DOTFILES_DIR) / "profiles"
    if not profiles_dir.exists():
        return repos

    for level1 in sorted(profiles_dir.iterdir()):
        if not level1.is_dir() or level1.name.startswith("."):
            continue

        # Check level 1: profiles/{repo}/.git
        if (level1 / ".git").exists():
            repos.append(level1)
        else:
            # Check level 2: profiles/{dir}/{repo}/.git
            for level2 in sorted(level1.iterdir()):
                if not level2.is_dir() or level2.name.startswith("."):
                    continue
                if (level2 / ".git").exists():
                    repos.append(level2)

    return repos


def sync_profile_repos(action: str) -> bool:
    """Sync all profile repos that are git repositories (pull or push).

    Non-git directories in profiles/ are silently skipped.

    Args:
        action: Either "pull" or "push"

    Returns:
        True if all repos synced successfully, False otherwise
    """
    repos = get_profile_repos()
    if not repos:
        return True

    profiles_dir = Path(DOTFILES_DIR) / "profiles"
    success = True
    for repo in repos:
        repo_rel_path = repo.relative_to(profiles_dir)
        if action == "pull":
            click.echo(f"Pulling profiles/{repo_rel_path}...")
            result = subprocess.call(["git", "pull"], cwd=repo)
        else:  # push
            click.echo(f"Pushing profiles/{repo_rel_path}...")
            # Get the default branch name for this repo
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
            )
            branch = (
                branch_result.stdout.strip()
                if branch_result.returncode == 0
                else "main"
            )
            result = subprocess.call(["git", "push", "origin", branch], cwd=repo)

        if result != 0:
            click.echo(
                f"Warning: git {action} failed for profiles/{repo_rel_path}", err=True
            )
            success = False

    return success

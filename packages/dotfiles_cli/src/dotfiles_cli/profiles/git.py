"""Git operations for profile repositories."""

from __future__ import annotations

import asyncio
import dataclasses
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


@dataclasses.dataclass
class RepoStatus:
    """Status information for a single git repository."""

    name: str
    branch: str
    dirty: bool
    untracked: int
    staged: int
    modified: int
    ahead: int
    behind: int
    has_remote: bool
    last_commit: str


async def _get_detailed_repo_status(name: str, repo_path: Path) -> RepoStatus:
    """Get detailed status for a single repo asynchronously."""
    branch_task = _run_git_command(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_path
    )
    status_task = _run_git_command(["git", "status", "--porcelain"], repo_path)
    tracking_task = _run_git_command(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo_path,
    )
    log_task = _run_git_command(
        ["git", "log", "-1", "--format=%s", "--date=short"], repo_path
    )

    branch_r, status_r, tracking_r, log_r = await asyncio.gather(
        branch_task, status_task, tracking_task, log_task
    )

    branch = branch_r.stdout.strip() if branch_r.returncode == 0 else "unknown"

    # Parse porcelain status
    staged = 0
    modified = 0
    untracked = 0
    for line in status_r.stdout.splitlines():
        if not line:
            continue
        index_status = line[0]
        worktree_status = line[1]
        if index_status == "?":
            untracked += 1
        else:
            if index_status not in (" ", "?"):
                staged += 1
            if worktree_status not in (" ", "?"):
                modified += 1

    dirty = bool(status_r.stdout.strip())

    # Check ahead/behind
    ahead = 0
    behind = 0
    has_remote = tracking_r.returncode == 0
    if has_remote:
        ahead_behind = await _run_git_command(
            ["git", "rev-list", "--left-right", "--count", "@{u}...HEAD"],
            repo_path,
        )
        if ahead_behind.returncode == 0:
            parts = ahead_behind.stdout.strip().split()
            if len(parts) == 2:
                behind = int(parts[0])
                ahead = int(parts[1])

    last_commit = log_r.stdout.strip() if log_r.returncode == 0 else ""

    return RepoStatus(
        name=name,
        branch=branch,
        dirty=dirty,
        untracked=untracked,
        staged=staged,
        modified=modified,
        ahead=ahead,
        behind=behind,
        has_remote=has_remote,
        last_commit=last_commit,
    )


def get_all_repo_statuses() -> list[RepoStatus]:
    """Get detailed status for all repos (main + profiles) asynchronously.

    Returns:
        List of RepoStatus for each repository
    """
    profiles_dir = Path(DOTFILES_DIR) / "profiles"

    async def check_all() -> list[RepoStatus]:
        repos = [("dotfiles", Path(DOTFILES_DIR))]
        for repo in get_profile_repos():
            rel = repo.relative_to(profiles_dir)
            repos.append((f"profiles/{rel}", repo))

        return list(
            await asyncio.gather(
                *[_get_detailed_repo_status(name, path) for name, path in repos]
            )
        )

    return asyncio.run(check_all())


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


async def _has_remote(repo: Path) -> bool:
    """Check if a git repository has at least one remote with a URL configured."""
    result = await _run_git_command(["git", "remote"], repo)
    if result.returncode != 0 or not result.stdout.strip():
        return False

    # Verify at least one remote has a URL (a remote can exist without a URL)
    for remote in result.stdout.strip().splitlines():
        url_result = await _run_git_command(["git", "remote", "get-url", remote], repo)
        if url_result.returncode == 0 and url_result.stdout.strip():
            return True

    return False


async def _sync_single_repo(
    action: str, repo: Path, profiles_dir: Path
) -> tuple[str, bool]:
    """Sync a single profile repo. Returns (display_name, success)."""
    repo_rel_path = repo.relative_to(profiles_dir)
    display_name = f"profiles/{repo_rel_path}"

    if not await _has_remote(repo):
        click.echo(f"Skipping {display_name} (no remote configured)")
        return display_name, True

    if action == "pull":
        click.echo(f"Pulling {display_name}...")
        result = await _run_git_command(["git", "pull"], repo)
    else:  # push
        branch_result = await _run_git_command(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], repo
        )
        branch = (
            branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
        )
        click.echo(f"Pushing {display_name}...")
        result = await _run_git_command(["git", "push", "origin", branch], repo)

    if result.returncode != 0:
        click.echo(f"Warning: git {action} failed for {display_name}", err=True)
        if result.stderr.strip():
            click.echo(f"  {result.stderr.strip()}", err=True)
        return display_name, False

    return display_name, True


def sync_profile_repos(action: str) -> bool:
    """Sync all profile repos that are git repositories (pull or push).

    Runs all repos in parallel for better performance.
    Non-git directories in profiles/ are silently skipped.
    Repos without a configured remote are skipped with a notice.

    Args:
        action: Either "pull" or "push"

    Returns:
        True if all repos synced successfully, False otherwise
    """
    repos = get_profile_repos()
    if not repos:
        return True

    profiles_dir = Path(DOTFILES_DIR) / "profiles"

    async def sync_all() -> bool:
        results = await asyncio.gather(
            *[_sync_single_repo(action, repo, profiles_dir) for repo in repos]
        )
        return all(success for _, success in results)

    return asyncio.run(sync_all())

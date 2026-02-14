"""Configuration schema definitions using Pydantic.

Note: Default values come from default.yml which ships with the package.
Pydantic model defaults here are only used as fallbacks during parsing.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a specific AI coding agent.

    Attributes:
        resume_args: Arguments to add for resume functionality.
    """

    resume_args: Annotated[list[str], Field(default_factory=list)]


class AgentsConfig(BaseModel):
    """Configuration for AI coding agents.

    Attributes:
        order: Priority order for agent detection.
        configs: Per-agent configuration.
    """

    order: Annotated[list[str], Field(default_factory=list)]
    configs: Annotated[dict[str, AgentConfig], Field(default_factory=dict)]


class ResumeConfig(BaseModel):
    """Configuration for resume behavior.

    Attributes:
        enabled: Whether --resume flag is enabled by default.
    """

    enabled: bool = False


class PostCreateCommand(BaseModel):
    """A command to run after creating a worktree.

    Attributes:
        command: Shell command to run.
        if_exists: Only run if this file exists in the worktree.
    """

    command: str
    if_exists: str | None = None


class AutoSelectConfig(BaseModel):
    """Configuration for auto-selecting a branch in worktree picker.

    When enabled, the worktree picker will automatically select the specified
    branch after a timeout. Any keypress cancels the timer, allowing users
    to still access agent selection (Ctrl+A) and other UI features.

    Attributes:
        enabled: Whether auto-select is enabled.
        branch: Branch to auto-select. Use "-" for repo's default branch.
        timeout: Seconds before auto-selection (0 for instant).
    """

    enabled: bool = False
    branch: str = "-"
    timeout: float = 3.0


class WorktreesConfig(BaseModel):
    """Configuration for git worktrees.

    Attributes:
        enabled: Whether worktrees feature is enabled.
        auto_select: Auto-select configuration for worktree picker.
        parent_dir: Directory for worktrees.
        use_home: Use ~/.git-worktrees/{repo}-{branch} instead.
        post_create: Commands to run after creating a worktree.
        copy_files: Files to copy from main repo to worktree.
        symlink_files: Files to symlink from main repo to worktree.
        resume: Default --resume flag for worktree sessions.
    """

    enabled: bool = True
    auto_select: Annotated[AutoSelectConfig, Field(default_factory=AutoSelectConfig)]
    parent_dir: str = ".worktrees"
    use_home: bool = False
    post_create: Annotated[list[PostCreateCommand], Field(default_factory=list)]
    copy_files: Annotated[list[str], Field(default_factory=list)]
    symlink_files: Annotated[list[str], Field(default_factory=list)]
    resume: bool = False


class ZellijConfig(BaseModel):
    """Configuration for Zellij terminal multiplexer.

    Attributes:
        layout: Layout name to use. If None, uses Zellij's default layout.
        session_name: Session name template.
    """

    layout: str | None = None
    session_name: str = "{repo}-{agent}"


class GitHubConfig(BaseModel):
    """Configuration for GitHub integration.

    Attributes:
        fetch_issues: Whether to fetch GitHub issues.
        issue_limit: Maximum number of issues to fetch.
    """

    fetch_issues: bool = True
    issue_limit: int = 20


class HiveConfig(BaseModel):
    """Root configuration for Hive CLI.

    Attributes:
        agents: Agent detection and configuration.
        resume: Resume behavior configuration.
        worktrees: Git worktree configuration.
        zellij: Zellij configuration.
        github: GitHub integration configuration.
    """

    agents: Annotated[AgentsConfig, Field(default_factory=AgentsConfig)]
    resume: Annotated[ResumeConfig, Field(default_factory=ResumeConfig)]
    worktrees: Annotated[WorktreesConfig, Field(default_factory=WorktreesConfig)]
    zellij: Annotated[ZellijConfig, Field(default_factory=ZellijConfig)]
    github: Annotated[GitHubConfig, Field(default_factory=GitHubConfig)]

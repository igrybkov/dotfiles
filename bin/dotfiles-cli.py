#!/usr/bin/env python
"""Thin wrapper for the dotfiles CLI.

This script loads environment variables and delegates to the dotfiles_cli package.
"""

import sys
from pathlib import Path

# Add packages directory to path for development
packages_dir = Path(__file__).parent.parent / "packages" / "dotfiles_cli" / "src"
if packages_dir.exists():
    sys.path.insert(0, str(packages_dir))

from dotenv import load_dotenv  # noqa: E402

from dotfiles_cli import cli  # noqa: E402
from dotfiles_cli.constants import DOTFILES_DIR  # noqa: E402
from dotfiles_cli.utils import preprocess_logfile_args  # noqa: E402


def main():
    """Main entry point for the dotfiles CLI."""
    # Load environment variables from .env file
    load_dotenv(dotenv_path=f"{DOTFILES_DIR}/.env")

    # Preprocess args to handle --logfile with optional argument
    sys.argv = [sys.argv[0]] + preprocess_logfile_args(sys.argv[1:])

    # Run the CLI
    exit_code: int | None = cli(prog_name="dotfiles")
    if exit_code is None:
        exit_code = 0
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

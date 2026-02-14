#!/bin/bash
# Custom file suggestion script for Claude Code
# Includes profiles/private/** while respecting gitignore elsewhere

# Read query from stdin (JSON format: {"query": "..."})
read -r input
query=$(echo "$input" | jq -r '.query // ""')

# Get the repo root
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root" || exit 1

{
    # Get all tracked files (respects gitignore)
    git ls-files 2>/dev/null

    # Add files from profiles/private/ (gitignored but we want them)
    find profiles/private -type f 2>/dev/null | grep -v '\.git'
} | sort -u | grep -i "$query"

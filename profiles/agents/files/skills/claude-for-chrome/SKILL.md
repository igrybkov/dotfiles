---
name: claude-for-chrome
description: Interact with Chrome browser using accessibility tree refs instead of screenshots
allowed-tools:
  - Bash
---

# Claude for Chrome

This skill provides guidance for interacting with Chrome browser using tree references and the accessibility tree.

## Core Principles

- **Use `read_page`** to get element refs from the accessibility tree
- **Use `find`** to locate elements by description
- **Click/interact using `ref`**, not coordinates
- **NEVER take screenshots** unless explicitly requested by the user

## Interactive CLIs with tmux

For interactive command-line interfaces, you can use tmux. The pattern is:

1. Start a tmux session
2. Send commands to it
3. Capture the output
4. Verify it's what you expect

## Why Tree Refs?

Tree references are more reliable and maintainable than:
- **Screenshots**: Can fail with visual changes, different screen sizes, or themes
- **Coordinates**: Break when page layout changes
- **XPath/CSS selectors**: Can be fragile and hard to maintain

The accessibility tree provides semantic references that are stable and meaningful.

## Best Practices

- Always use `read_page` first to understand the page structure
- Use `find` with descriptive text to locate elements (e.g., "Submit button", "Email input field")
- Reference elements by their `ref` value when interacting
- Verify successful interactions by reading the page state again

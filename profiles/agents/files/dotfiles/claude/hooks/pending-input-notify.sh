#!/usr/bin/env bash
#
# Claude Code Notification Hook: Desktop notification when pending input
#
# This hook runs when Claude Code needs user attention.
# It sends a macOS desktop notification with optional Zellij context.
#
# Hook event: Notification
# Supported matchers: idle_prompt, permission_prompt
#

set -euo pipefail

# Read JSON input from stdin
input=$(cat)

# Extract notification type using jq (fallback to grep if jq unavailable)
if command -v jq &> /dev/null; then
    notification_type=$(echo "$input" | jq -r '.notification_type // "unknown"')
else
    notification_type=$(echo "$input" | grep -o '"notification_type":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
fi

# Build notification title with Zellij context if available
title="Claude Code"

if [[ -n "${ZELLIJ_SESSION_NAME:-}" ]]; then
    title="Claude Code [${ZELLIJ_SESSION_NAME}]"

    # Add tab info if available (ZELLIJ_PANE_ID format: tab_id/pane_id)
    if [[ -n "${ZELLIJ_PANE_ID:-}" ]]; then
        # Extract tab number from pane ID (format varies, try common patterns)
        tab_info="${ZELLIJ_PANE_ID%%/*}"
        if [[ -n "$tab_info" ]]; then
            title="Claude Code [${ZELLIJ_SESSION_NAME}:${tab_info}]"
        fi
    fi
fi

# Set message based on notification type
case "$notification_type" in
    permission_prompt)
        message="🔐 Permission required"
        ;;
    idle_prompt)
        message="💬 Waiting for your input"
        ;;
    *)
        message="Needs attention"
        ;;
esac

# Claude app icon path
claude_app="/Applications/Claude.app"

# Send notification using terminal-notifier (preferred) or osascript (fallback)
if command -v terminal-notifier &> /dev/null; then
    args=(
        -title "$title"
        -message "$message"
        -sound "Blow"
        -group "claude-code"
    )
    # Add app icon if Claude.app exists
    if [[ -d "$claude_app" ]]; then
        args+=(-appIcon "$claude_app/Contents/Resources/AppIcon.icns")
    fi
    terminal-notifier "${args[@]}"
else
    # Fallback to osascript (no custom icon support)
    osascript -e "display notification \"$message\" with title \"$title\" sound name \"Blow\""
fi

exit 0

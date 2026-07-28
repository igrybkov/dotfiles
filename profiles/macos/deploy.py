"""macOS system defaults deploy.

Ports ``profiles/macos/roles/macos/tasks/main.yml`` to pyinfra:
  - Touch ID for sudo (writes /etc/pam.d/sudo_local, needs root).
  - All ``community.general.osx_defaults`` entries via the idempotent
    ``set_default`` operation.
  - Dock / Finder are restarted only when a setting they own actually changed
    (mirrors the Ansible ``notify: Restart Dock``/``Restart Finder`` handlers).

Behavior note vs. the Ansible role: the Ansible task auto-created the
``.cache/skip-macos`` marker after its first successful run (the role was slow,
~8s). ``set_default`` is now build-time idempotent and cheap to re-run, so we
only *honor* the marker — we no longer create it automatically. Users can still
opt out with ``dotfiles cache create skip-macos``.
"""

from __future__ import annotations

import io
import platform
from pathlib import Path

from pyinfra.operations import files, server

from dotfiles_pyinfra.operations.osx_defaults import set_default
from dotfiles_pyinfra.tags import tag_selected


def deploy(tags: set[str], dotfiles_dir: Path) -> None:
    if not tag_selected("macos", tags):
        return

    # Only meaningful on macOS — the Ansible role gated on distribution == MacOSX.
    if platform.system() != "Darwin":
        return

    # Skip if cache marker exists (dotfiles cache create skip-macos).
    skip_marker = dotfiles_dir / ".cache" / "skip-macos"
    if skip_marker.exists():
        return

    # -----------------------------------------------------------------------
    # Touch ID for sudo
    # -----------------------------------------------------------------------
    files.put(
        name="Enable Touch ID for sudo",
        src=io.BytesIO(b"auth sufficient pam_tid.so\n"),
        dest="/etc/pam.d/sudo_local",
        user="root",
        group="wheel",
        mode="644",
        _sudo=True,
    )

    # -----------------------------------------------------------------------
    # Software / app updates and general behavior
    # -----------------------------------------------------------------------
    set_default(
        name='[macOS] Disable "Are you sure to open this application?" dialog',
        domain="com.apple.LaunchServices",
        key="LSQuarantine",
        type_="bool",
        value=False,
    )
    set_default(
        name="[macOS] Check for software updates daily, not just once per week",
        domain="com.apple.SoftwareUpdate",
        key="ScheduleFrequency",
        type_="integer",
        value=1,
    )
    set_default(
        name="[macOS] Download newly available updates in background",
        domain="com.apple.SoftwareUpdate",
        key="AutomaticDownload",
        type_="bool",
        value=True,
    )
    set_default(
        name="[macOS] Install System data files & security updates",
        domain="com.apple.SoftwareUpdate",
        key="CriticalUpdateInstall",
        type_="bool",
        value=True,
    )
    set_default(
        name="[macOS] Turn on app auto-update",
        domain="com.apple.commerce",
        key="AutoUpdate",
        type_="bool",
        value=True,
    )

    # -----------------------------------------------------------------------
    # Trackpad
    # -----------------------------------------------------------------------
    set_default(
        name="[macOS] Trackpad - Increase speed of trackpad cursor movement",
        domain="NSGlobalDomain",
        key="com.apple.trackpad.scaling",
        type_="float",
        value=3,
    )
    set_default(
        name="[macOS] Trackpad - Enable force click and haptic feedback",
        domain="com.apple.driver.AppleBluetoothMultitouch.trackpad",
        key="ActuateDetents",
        type_="integer",
        value=1,
    )
    set_default(
        name="[macOS] Trackpad - Swipe between pages with two fingers",
        domain="com.apple.driver.AppleBluetoothMultitouch.trackpad",
        key="TrackpadThreeFingerHorizSwipeGesture",
        type_="integer",
        value=2,
    )
    set_default(
        name="[macOS] Trackpad - Swipe three fingers up to show Mission Control",
        domain="com.apple.driver.AppleBluetoothMultitouch.trackpad",
        key="TrackpadThreeFingerVertSwipeGesture",
        type_="integer",
        value=2,
    )

    # -----------------------------------------------------------------------
    # Keyboard
    # -----------------------------------------------------------------------
    set_default(
        name="[macOS] Disable smart quotes (annoying when typing code)",
        domain="NSGlobalDomain",
        key="NSAutomaticQuoteSubstitutionEnabled",
        type_="bool",
        value=False,
    )
    set_default(
        name="[macOS] Disable smart dashes (annoying when typing code)",
        domain="NSGlobalDomain",
        key="NSAutomaticDashSubstitutionEnabled",
        type_="bool",
        value=False,
    )
    set_default(
        name="[macOS] Keyboard - Auto-illuminate built-in keyboard in low light",
        domain="com.apple.BezelServices",
        key="kDim",
        type_="bool",
        value=True,
    )
    set_default(
        name="[macOS] Keyboard - Turn off illumination after 5 minutes idle",
        domain="com.apple.BezelServices",
        key="kDimTime",
        type_="integer",
        value=300,
    )
    set_default(
        name="[macOS] Keyboard - Enable function keys",
        domain="NSGlobalDomain",
        key="com.apple.keyboard.fnState",
        type_="integer",
        value=1,
    )

    # -----------------------------------------------------------------------
    # Dock (restart only if something changed)
    # -----------------------------------------------------------------------
    dock_changed = any(
        [
            set_default(
                name="[macOS] Dock - Show on all displays",
                domain="com.apple.dock",
                key="appswitcher-all-displays",
                type_="bool",
                value=True,
            ),
            set_default(
                name="[macOS] Dock - Show on the left",
                domain="com.apple.dock",
                key="orientation",
                type_="string",
                value="bottom",
            ),
            set_default(
                name="[macOS] Dock - Set auto-hide delay",
                domain="com.apple.dock",
                key="autohide-delay",
                type_="float",
                value=0,
            ),
            set_default(
                name="[macOS] Dock - Automatically hide and show",
                domain="com.apple.dock",
                key="autohide",
                type_="bool",
                value=True,
            ),
            set_default(
                name="[macOS] Dock - Set icon size",
                domain="com.apple.dock",
                key="tilesize",
                type_="float",
                value=48,
            ),
            set_default(
                name="[macOS] Dock - Enable magnification",
                domain="com.apple.dock",
                key="magnification",
                type_="bool",
                value=True,
            ),
            set_default(
                name="[macOS] Dock - Set magnification size",
                domain="com.apple.dock",
                key="largesize",
                type_="float",
                value=112,
            ),
            set_default(
                name="[macOS] Dock - Minimize windows into application icon",
                domain="com.apple.dock",
                key="minimize-to-application",
                type_="bool",
                value=True,
            ),
            set_default(
                name="[macOS] Dock - Don't show recent applications in Dock",
                domain="com.apple.dock",
                key="show-recents",
                type_="bool",
                value=False,
            ),
        ]
    )

    # -----------------------------------------------------------------------
    # Finder (restart only if something changed)
    # -----------------------------------------------------------------------
    finder_changed = set_default(
        name="[macOS] Finder - Show the ~/Library folder",
        domain="com.apple.finder",
        key="ShowLibraryFolder",
        type_="bool",
        value=True,
    )
    # Default sort order to 'Name' — same value across three keys.
    for sort_key in (
        "FK_DefaultIconViewSettings:arrangeBy",
        "FK_StandardViewSettings:IconViewSettings:arrangeBy",
        "StandardViewSettings:IconViewSettings:arrangeBy",
    ):
        if set_default(
            name=f"[macOS] Finder - Set default sort order to 'Name' ({sort_key})",
            domain="com.apple.finder",
            key=sort_key,
            type_="string",
            value="name",
        ):
            finder_changed = True

    # -----------------------------------------------------------------------
    # Restart affected services only when their settings changed.
    # `|| true` keeps the run green if the process isn't currently running.
    # -----------------------------------------------------------------------
    if dock_changed:
        server.shell(
            name="Restart Dock after changes",
            commands=["killall Dock || true"],
        )
    if finder_changed:
        server.shell(
            name="Restart Finder after changes",
            commands=["killall Finder || true"],
        )

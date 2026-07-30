#!/usr/bin/env bash
# SUDO_ASKPASS helper for unattended Ansible runs.
#
# Ansible tasks have no attached tty, so any sudo call made without an
# explicit `become` (e.g. a cask postflight shelling out to sudo directly,
# such as docker-desktop symlinking CLI tools into /usr/local/bin) would
# otherwise block forever waiting for input that can never arrive. Tools that
# check SUDO_ASKPASS (e.g. Homebrew, which passes `-A` to sudo(8) when it's
# set) run this script instead and read the password from its stdout.
#
# The password is the one already collected (and validated) by the CLI's own
# `SUDO password:` prompt at the start of the run, passed through via an env
# var so no separate/duplicate prompt is needed.
printf '%s' "$DOTFILES_SUDO_ASKPASS_PASSWORD"

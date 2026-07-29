"""Fresh-exec entry point: print this machine's age key to stdout, or nothing.

Exists solely so a caller that must not touch the macOS Security framework
in-process after a ``fork()`` without ``exec()`` — e.g. Ansible's forked
lookup-plugin workers — can fetch the key via a fresh subprocess instead.
python-keyring's Security-framework calls abort the process when made after
such a fork; running here in a brand-new process sidesteps that entirely.
See ``age.read_age_key_via_subprocess``, the caller of this module.
"""

from .age import read_age_key

if __name__ == "__main__":
    _key = read_age_key()
    if _key:
        print(_key, end="")

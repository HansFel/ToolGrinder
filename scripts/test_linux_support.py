#!/usr/bin/env python3
"""Simple checks for Linux compatibility: tkinter availability, DISPLAY, paramiko and keyring presence."""
import sys
import os

print('Platform:', sys.platform)

# tkinter
try:
    import tkinter
    print('tkinter: OK')
    if sys.platform.startswith('linux'):
        if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
            print('Display available')
        else:
            print('No DISPLAY/WAYLAND_DISPLAY set - GUI likely unavailable')
except Exception as e:
    print('tkinter: MISSING', e)

# paramiko
try:
    import paramiko
    print('paramiko: OK (version', paramiko.__version__ + ')')
except Exception as e:
    print('paramiko: MISSING', e)

# keyring
try:
    import keyring
    print('keyring: OK (backend)', keyring.get_keyring())
except Exception as e:
    print('keyring: MISSING or no backend', e)

print('\nCheck complete. If something is missing, install packages with your distro package manager and pip (see manual).')

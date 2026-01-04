"""
Build script für Releases:
- Erzeugt eine Ein-Datei-EXE mittels PyInstaller
- Optional: Icon einbinden (pass path via --icon)
- Legt eine ZIP mit EXE und README_BUILD.txt im Verzeichnis 'dist' ab

Usage: python scripts/build_release.py [--icon path/to/icon.ico] [--name Grinder] [--version 1.0.0]
"""
import argparse
import os
import shutil
import subprocess
import sys
from zipfile import ZipFile

ROOT = os.path.dirname(os.path.dirname(__file__))
DIST = os.path.join(ROOT, 'dist')
BUILD = os.path.join(ROOT, 'build')
SPEC = os.path.join(ROOT, 'Grinder.spec')

parser = argparse.ArgumentParser()
parser.add_argument('--icon', help='Pfad zur .ico Datei (optional)', default=None)
parser.add_argument('--name', help='Name der EXE (default: Grinder)', default='Grinder')
parser.add_argument('--version', help='Version string for release name', default='1.0.0')
parser.add_argument('--include-servers', action='store_true', help='Fügt .grinder_servers.json zur Release-ZIP hinzu (falls vorhanden)')
args = parser.parse_args()

icon = args.icon
name = args.name
version = args.version
include_servers = args.include_servers

pyinstaller_cmd = [sys.executable, '-m', 'PyInstaller', '--onefile', '--name', name, '--console', 'Grinder.py']
# ensure keyring and paramiko are included as hidden imports for the exe to work with uploads
pyinstaller_cmd.extend(['--hidden-import', 'paramiko', '--hidden-import', 'keyring'])
if icon and os.path.exists(icon):
    pyinstaller_cmd.insert(-1, '--icon')
    pyinstaller_cmd.insert(-1, icon)
print('Running PyInstaller...')
ret = subprocess.run(pyinstaller_cmd)
if ret.returncode != 0:
    print('PyInstaller build failed', file=sys.stderr)
    sys.exit(1)

exe_path = os.path.join(DIST, f'{name}.exe')
if not os.path.exists(exe_path):
    print('Expected EXE not found:', exe_path, file=sys.stderr)
    sys.exit(1)

# Prepare release ZIP
zip_name = os.path.join(DIST, f'{name}_v{version}.zip')
with ZipFile(zip_name, 'w') as z:
    z.write(exe_path, arcname=os.path.basename(exe_path))
    # README
    readme = os.path.join(DIST, 'README_BUILD.txt')
    with open(readme, 'w', encoding='utf-8') as f:
        f.write(f"{name} v{version} - Release\n\nIncludes: {os.path.basename(exe_path)}\n\nUsage:\n  {os.path.basename(exe_path)} -c ToolLib/template1.json\n\nOptional: .grinder_servers.json can be included with --include-servers when building the release.\n")
    z.write(readme, arcname='README_BUILD.txt')
    # optionally include servers file
    if include_servers and os.path.exists(os.path.join(ROOT, '.grinder_servers.json')):
        z.write(os.path.join(ROOT, '.grinder_servers.json'), arcname='.grinder_servers.json')

print('Release ZIP created:', zip_name)
print('Build finished successfully.')

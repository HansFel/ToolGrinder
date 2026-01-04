#!/usr/bin/env python3
"""Ein kleines Hilfs-Skript zum Erzeugen von SSH-Key-Paaren.
Versucht zuerst, `ssh-keygen` zu verwenden; fällt das aus, nutzt es `paramiko` wenn verfügbar.

Usage:
  python scripts/gen_ssh_key.py --type ed25519 --output mykey --comment "me@example.com" --passphrase
"""

import argparse
import os
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--type', choices=['ed25519', 'rsa'], default='ed25519', help='Key type')
parser.add_argument('--bits', type=int, default=4096, help='RSA bits (only for rsa)')
parser.add_argument('--output', help='Output filename prefix (default: id_{type})')
parser.add_argument('--comment', default='', help='Comment for public key')
parser.add_argument('--passphrase', action='store_true', help='Prompt for passphrase to protect the private key')
parser.add_argument('--force', action='store_true', help='Overwrite existing files')
args = parser.parse_args()

kt = args.type
bits = args.bits
out = args.output or f"id_{kt}"
pub = out + '.pub'
priv = out

# Try to use ssh-keygen if available
shutil_which = None
try:
    from shutil import which as shutil_which
except Exception:
    shutil_which = None

if shutil_which and shutil_which('ssh-keygen'):
    cmd = ['ssh-keygen', '-t', kt, '-f', priv]
    if kt == 'rsa':
        cmd.extend(['-b', str(bits)])
    if args.comment:
        cmd.extend(['-C', args.comment])
    if not args.passphrase:
        cmd.extend(['-N', ''])
    print('Running:', ' '.join(cmd))
    ret = subprocess.run(cmd)
    if ret.returncode == 0:
        print('Keys written:', priv, pub)
        sys.exit(0)
    else:
        print('ssh-keygen failed, falling back to paramiko if available')

# Fallback: paramiko if installed
try:
    import paramiko
except Exception:
    print('Neither ssh-keygen nor paramiko available. Please install paramiko or use ssh-keygen.')
    sys.exit(2)

# Generate keys using paramiko
if os.path.exists(priv) and not args.force:
    print('File exists:', priv)
    sys.exit(1)

if kt == 'rsa':
    key = paramiko.RSAKey.generate(bits)
else:
    # Ed25519
    try:
        key = paramiko.Ed25519Key.generate()
    except Exception:
        # Older paramiko versions might not support Ed25519Key.generate(); try RSA fallback
        print('Ed25519 generation not supported by paramiko; generating RSA instead')
        key = paramiko.RSAKey.generate(bits if bits else 4096)

# Write private key
if args.passphrase:
    import getpass
    pw = getpass.getpass('Passphrase for private key (empty for none): ')
else:
    pw = None

key.write_private_key_file(priv, password=pw)
# Write public key (OpenSSH format)
pubdata = f"{key.get_name()} {key.get_base64()} {args.comment}\n"
with open(pub, 'w', encoding='utf-8') as f:
    f.write(pubdata)

print('Keys written:', priv, pub)
print('Public key (preview):')
print(pubdata)
print('\nTip: Copy the public key to your server into ~/.ssh/authorized_keys')

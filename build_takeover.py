"""
Build TennetTakeover.exe — portable injector with file picker.

  python build_takeover.py

Output: dist/TennetTakeover.exe
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TAKEOVER = os.path.join(ROOT, 'takeover.py')
DIST = os.path.join(ROOT, 'dist')
BUILD = os.path.join(ROOT, 'build', 'takeover-pyi')

HIDDEN = [
    'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES',
    'win32crypt', 'pywintypes', 'pythoncom',
    'websocket', 'requests',
    'tkinter', 'tkinter.filedialog',
]


def main():
    if not os.path.exists(TAKEOVER):
        print('[!] takeover.py not found')
        sys.exit(1)

    os.makedirs(DIST, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)

    hidden_args = []
    for mod in HIDDEN:
        hidden_args.extend(['--hidden-import', mod])

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--console',
        '--clean',
        '--name', 'TennetTakeover',
        '--distpath', DIST,
        '--workpath', BUILD,
        '--specpath', BUILD,
        '--noupx',
        *hidden_args,
        TAKEOVER,
    ]

    print('[*] Building TennetTakeover.exe ...')
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(1)

    out = os.path.join(DIST, 'TennetTakeover.exe')
    if os.path.exists(out):
        mb = os.path.getsize(out) / (1024 * 1024)
        print(f'[+] Done: {out} ({mb:.1f} MB)')
        print('[*] Double-click TennetTakeover.exe → pick zip → choose browser → inject')
    else:
        print('[!] TennetTakeover.exe not found')
        sys.exit(1)


if __name__ == '__main__':
    main()

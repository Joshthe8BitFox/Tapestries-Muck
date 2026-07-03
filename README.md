# Tapestries MUCK Client

<img width="1680" height="1021" alt="image" src="https://github.com/user-attachments/assets/27d7915d-0c30-45dc-84f0-b57fffcfa0b5" />


A small cross-platform desktop client for Tapestries MUCK, written in Python with PySide6.

Current version: `0.2.2`

## Downloads

If setting up Python feels like too much fuss, compiled builds are available on the GitHub Releases page.

- macOS Apple Silicon: download `Tapestries-MUCK-Client-v0.2.2-macos-arm64.dmg`, open it, and drag the app to Applications.
- Windows: download `Tapestries-MUCK-Client-v0.2.0-windows-x64.zip`, extract it, and run `Tapestries-MUCK-Client.exe`.

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

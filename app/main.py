from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .database import Database
from .settings_store import SettingsStore
from .ui.main_window import MainWindow


def _application_icon_path() -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root / "assets" / "icons" / "tapestries-muck.png"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("TapestriesMuck")
    app.setApplicationDisplayName("TapestriesMuck")
    app.setOrganizationName("Tapestries")
    app.setDesktopFileName("tapestries-muck-client")
    icon = QIcon(str(_application_icon_path()))
    app.setWindowIcon(icon)
    db = Database(Path("client_data.sqlite3"))
    settings_store = SettingsStore(db)
    window = MainWindow(db, settings_store)
    window.setWindowIcon(icon)
    window.show()
    return app.exec()

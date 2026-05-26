from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .database import Database
from .settings_store import SettingsStore
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    db = Database(Path("client_data.sqlite3"))
    settings_store = SettingsStore(db)
    window = MainWindow(db, settings_store)
    window.show()
    return app.exec()

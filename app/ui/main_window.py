from __future__ import annotations

import re

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QFontDatabase, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QApplication,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFontComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..database import Database
from ..network import MuckConnection
from ..parser import KeywordRule, LineParser, ParsedLine
from ..settings_store import ClientSettings, SettingsStore
from ..version import __version__


URL_PATTERN = re.compile(r"\b(?:https?://|www\.)[^\s<>()]+[^\s<>().,!?:;'\"]", re.IGNORECASE)
MAX_INPUT_LENGTH = 1000


class ClickableOutputTextEdit(QTextEdit):
    def mouseReleaseEvent(self, event) -> None:
        href = self.anchorAt(event.position().toPoint())
        if href:
            QDesktopServices.openUrl(QUrl(href))
            return
        super().mouseReleaseEvent(event)


class ColorButton(QPushButton):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color if QColor(color).isValid() else "#ffffff"
        self.clicked.connect(self.pick_color)
        self._refresh()

    @property
    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color if QColor(color).isValid() else "#ffffff"
        self._refresh()

    def pick_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, "Pick color")
        if chosen.isValid():
            self._color = chosen.name()
            self._refresh()

    def _refresh(self) -> None:
        self.setText(self._color)
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color}; color: {self._readable_text_color(self._color)}; }}"
        )

    def _readable_text_color(self, color: str) -> str:
        qcolor = QColor(color)
        brightness = (qcolor.red() * 299 + qcolor.green() * 587 + qcolor.blue() * 114) / 1000
        return "#000000" if brightness > 150 else "#ffffff"


class CommandLineEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history: list[str] = []
        self.history_index: int | None = None
        self.completions: list[str] = []
        self._completion_start: int | None = None
        self._completion_prefix = ""
        self._completion_matches: list[str] = []
        self._completion_index = -1
        self._applying_completion = False
        self.textChanged.connect(self._reset_completion_unless_applying)

    def add_history(self, command: str) -> None:
        command = command.rstrip()
        if not command:
            return
        if not self.history or self.history[-1] != command:
            self.history.append(command)
        self.history_index = None

    def set_completions(self, names: list[str]) -> None:
        self.completions = sorted(set(names), key=str.lower)
        self._reset_completion()

    def event(self, event) -> bool:
        # Qt normally uses Tab for focus traversal before QLineEdit.keyPressEvent()
        # sees it. Intercept it here so Tab can autocomplete MUCK usernames.
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self._complete_current_word(reverse=event.key() == Qt.Key.Key_Backtab)
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Up:
            self._reset_completion()
            self._history_up()
            return
        if event.key() == Qt.Key.Key_Down:
            self._reset_completion()
            self._history_down()
            return
        if event.key() == Qt.Key.Key_Tab:
            self._complete_current_word()
            return
        self._reset_completion()
        super().keyPressEvent(event)

    def _history_up(self) -> None:
        if not self.history:
            return
        if self.history_index is None:
            self.history_index = len(self.history) - 1
        else:
            self.history_index = max(0, self.history_index - 1)
        self.setText(self.history[self.history_index])
        self.setCursorPosition(len(self.text()))

    def _history_down(self) -> None:
        if self.history_index is None:
            return
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self.clear()
            return
        self.setText(self.history[self.history_index])
        self.setCursorPosition(len(self.text()))

    def _complete_current_word(self, reverse: bool = False) -> None:
        text = self.text()
        pos = self.cursorPosition()
        if self._completion_start is None or pos < self._completion_start:
            self._start_completion_session(text, pos)
        if not self._completion_matches or self._completion_start is None:
            return
        step = -1 if reverse else 1
        self._completion_index = (self._completion_index + step) % len(self._completion_matches)
        match = self._completion_matches[self._completion_index]
        end = pos
        new_text = text[:self._completion_start] + match + text[end:]
        self._applying_completion = True
        try:
            self.setText(new_text)
        finally:
            self._applying_completion = False
        self.setCursorPosition(self._completion_start + len(match))

    def _start_completion_session(self, text: str, pos: int) -> None:
        start = pos
        while start > 0 and not text[start - 1].isspace():
            start -= 1
        prefix = text[start:pos]
        self._completion_start = start if prefix else None
        self._completion_prefix = prefix
        self._completion_index = -1
        self._completion_matches = [
            name for name in self.completions if name.lower().startswith(prefix.lower())
        ] if prefix else []

    def _reset_completion_unless_applying(self, _text: str) -> None:
        if not self._applying_completion:
            self._reset_completion()

    def _reset_completion(self) -> None:
        self._completion_start = None
        self._completion_prefix = ""
        self._completion_matches = []
        self._completion_index = -1


class KeywordEditorDialog(QDialog):
    def __init__(
        self,
        title: str,
        keyword: str = "",
        enabled: bool = True,
        case_sensitive: bool = False,
        whole_word: bool = True,
        color: str = "#5dade2",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QFormLayout(self)
        self.keyword_edit = QLineEdit(keyword)
        self.enabled_box = QCheckBox("Enabled")
        self.enabled_box.setChecked(enabled)
        self.case_box = QCheckBox("Case sensitive")
        self.case_box.setChecked(case_sensitive)
        self.whole_box = QCheckBox("Whole word only")
        self.whole_box.setChecked(whole_word)
        self.color_button = ColorButton(color)
        layout.addRow("Keyword", self.keyword_edit)
        layout.addRow("Color", self.color_button)
        layout.addRow("", self.enabled_box)
        layout.addRow("", self.case_box)
        layout.addRow("", self.whole_box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, bool, bool, bool, str]:
        return (
            self.keyword_edit.text().strip(),
            self.enabled_box.isChecked(),
            self.case_box.isChecked(),
            self.whole_box.isChecked(),
            self.color_button.color,
        )


class KnownUserEditorDialog(QDialog):
    def __init__(
        self,
        title: str,
        username: str = "",
        gender: str | None = None,
        color: str | None = None,
        default_color: str = "#a8e6a3",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QFormLayout(self)
        self.username_edit = QLineEdit(username)
        self.gender_edit = QLineEdit(gender or "unknown")
        self.color_button = ColorButton(color or default_color)
        layout.addRow("Username", self.username_edit)
        layout.addRow("Gender", self.gender_edit)
        layout.addRow("Color", self.color_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[str, str | None, str]:
        gender = self.gender_edit.text().strip() or None
        return self.username_edit.text().strip(), gender, self.color_button.color


class SettingsDialog(QDialog):
    def __init__(self, db: Database, settings: ClientSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(680, 540)
        self.db = db
        self._settings = settings

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        connection_tab = QWidget()
        connection_layout = QFormLayout(connection_tab)
        self.host_edit = QLineEdit(settings.host)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(settings.port)
        self.ssl_box = QCheckBox("Use SSL")
        self.ssl_box.setChecked(settings.use_ssl)
        connection_layout.addRow("Host", self.host_edit)
        connection_layout.addRow("Port", self.port_spin)
        connection_layout.addRow("", self.ssl_box)
        tabs.addTab(connection_tab, "Connection")

        highlight_tab = QWidget()
        highlight_layout = QFormLayout(highlight_tab)
        self.mentions_box = QCheckBox("Highlight my name")
        self.mentions_box.setChecked(settings.auto_highlight_mentions)
        self.usernames_box = QCheckBox("Highlight known usernames")
        self.usernames_box.setChecked(settings.auto_highlight_usernames)
        self.whispers_box = QCheckBox("Highlight whispers")
        self.whispers_box.setChecked(settings.highlight_whispers)
        self.pages_box = QCheckBox("Highlight pages")
        self.pages_box.setChecked(settings.highlight_pages)
        self.look_smell_box = QCheckBox("Highlight looked at / smelled")
        self.look_smell_box.setChecked(settings.highlight_look_smell)
        highlight_layout.addRow("", self.mentions_box)
        highlight_layout.addRow("", self.usernames_box)
        highlight_layout.addRow("", self.whispers_box)
        highlight_layout.addRow("", self.pages_box)
        highlight_layout.addRow("", self.look_smell_box)
        tabs.addTab(highlight_tab, "Highlights")

        colors_tab = QWidget()
        colors_layout = QFormLayout(colors_tab)
        self.color_plain = ColorButton(settings.color_plain)
        self.color_echo = ColorButton(settings.color_echo)
        self.color_self = ColorButton(settings.color_self)
        self.color_keyword_default = ColorButton(settings.color_keyword_default)
        self.color_known_user_default = ColorButton(settings.color_known_user_default)
        self.color_page_received = ColorButton(settings.color_page_received)
        self.color_page_sent = ColorButton(settings.color_page_sent)
        self.color_whisper_received = ColorButton(settings.color_whisper_received)
        self.color_whisper_sent = ColorButton(settings.color_whisper_sent)
        self.color_looked_at = ColorButton(settings.color_looked_at)
        self.color_smelled = ColorButton(settings.color_smelled)
        colors_layout.addRow("Normal text", self.color_plain)
        colors_layout.addRow("Command echo", self.color_echo)
        colors_layout.addRow("Your name", self.color_self)
        colors_layout.addRow("Default keyword", self.color_keyword_default)
        colors_layout.addRow("Default known username", self.color_known_user_default)
        colors_layout.addRow("Received page", self.color_page_received)
        colors_layout.addRow("Sent page", self.color_page_sent)
        colors_layout.addRow("Received whisper", self.color_whisper_received)
        colors_layout.addRow("Sent whisper", self.color_whisper_sent)
        colors_layout.addRow("Looked at", self.color_looked_at)
        colors_layout.addRow("Smelled / sniffed", self.color_smelled)
        tabs.addTab(colors_tab, "Colors")

        font_tab = QWidget()
        font_layout = QFormLayout(font_tab)
        self.font_combo = QFontComboBox()
        self.font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        self.font_combo.setCurrentFont(QFont(settings.font_family))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 36)
        self.font_size_spin.setValue(settings.font_size)
        font_layout.addRow("Font", self.font_combo)
        font_layout.addRow("Size", self.font_size_spin)
        tabs.addTab(font_tab, "Font")

        keywords_tab = QWidget()
        keywords_layout = QVBoxLayout(keywords_tab)
        self.keyword_list = QListWidget()
        self.keyword_list.itemDoubleClicked.connect(lambda _item: self._edit_keyword())
        keywords_layout.addWidget(self.keyword_list)
        key_buttons = QHBoxLayout()
        add_key = QPushButton("Add")
        edit_key = QPushButton("Edit")
        remove_key = QPushButton("Remove")
        key_buttons.addWidget(add_key)
        key_buttons.addWidget(edit_key)
        key_buttons.addWidget(remove_key)
        keywords_layout.addLayout(key_buttons)
        add_key.clicked.connect(self._add_keyword)
        edit_key.clicked.connect(self._edit_keyword)
        remove_key.clicked.connect(self._remove_keyword)
        tabs.addTab(keywords_tab, "Keywords")

        users_tab = QWidget()
        users_layout = QVBoxLayout(users_tab)
        self.user_list = QListWidget()
        self.user_list.itemDoubleClicked.connect(lambda _item: self._edit_user())
        users_layout.addWidget(self.user_list)
        user_buttons = QHBoxLayout()
        add_user = QPushButton("Add")
        edit_user = QPushButton("Edit")
        remove_user = QPushButton("Remove")
        user_buttons.addWidget(add_user)
        user_buttons.addWidget(edit_user)
        user_buttons.addWidget(remove_user)
        users_layout.addLayout(user_buttons)
        add_user.clicked.connect(self._add_user)
        edit_user.clicked.connect(self._edit_user)
        remove_user.clicked.connect(self._remove_user)
        tabs.addTab(users_tab, "Known Users")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._reload_keywords()
        self._reload_users()

    def get_settings(self) -> ClientSettings:
        return ClientSettings(
            host=self.host_edit.text().strip(),
            port=self.port_spin.value(),
            use_ssl=self.ssl_box.isChecked(),
            auto_highlight_mentions=self.mentions_box.isChecked(),
            auto_highlight_usernames=self.usernames_box.isChecked(),
            highlight_whispers=self.whispers_box.isChecked(),
            highlight_pages=self.pages_box.isChecked(),
            highlight_look_smell=self.look_smell_box.isChecked(),
            color_plain=self.color_plain.color,
            color_echo=self.color_echo.color,
            color_page_received=self.color_page_received.color,
            color_page_sent=self.color_page_sent.color,
            color_whisper_received=self.color_whisper_received.color,
            color_whisper_sent=self.color_whisper_sent.color,
            color_self=self.color_self.color,
            color_keyword_default=self.color_keyword_default.color,
            color_known_user_default=self.color_known_user_default.color,
            color_looked_at=self.color_looked_at.color,
            color_smelled=self.color_smelled.color,
            font_family=self.font_combo.currentFont().family(),
            font_size=self.font_size_spin.value(),
            gender_colors=self._settings.gender_colors,
        )

    def _reload_keywords(self) -> None:
        self.keyword_list.clear()
        for row in self.db.list_keywords():
            color = row["color"] or self._settings.color_keyword_default
            label = f"{row['keyword']}  {color}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row["keyword"])
            item.setForeground(QColor(color))
            self.keyword_list.addItem(item)

    def _selected_keyword_row(self):
        item = self.keyword_list.currentItem()
        if not item:
            return None
        keyword = item.data(Qt.ItemDataRole.UserRole)
        for row in self.db.list_keywords():
            if row["keyword"] == keyword:
                return row
        return None

    def _add_keyword(self) -> None:
        dialog = KeywordEditorDialog(
            "Add keyword",
            color=self.color_keyword_default.color,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        keyword, enabled, case_sensitive, whole_word, color = dialog.values()
        if keyword:
            self.db.add_keyword(keyword, case_sensitive, whole_word, color)
            if not enabled:
                self.db.update_keyword(keyword, keyword, False, case_sensitive, whole_word, color)
            self._reload_keywords()

    def _edit_keyword(self) -> None:
        row = self._selected_keyword_row()
        if not row:
            return
        dialog = KeywordEditorDialog(
            "Edit keyword",
            keyword=row["keyword"],
            enabled=bool(row["enabled"]),
            case_sensitive=bool(row["case_sensitive"]),
            whole_word=bool(row["whole_word"]),
            color=row["color"] or self.color_keyword_default.color,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        keyword, enabled, case_sensitive, whole_word, color = dialog.values()
        if keyword:
            self.db.update_keyword(row["keyword"], keyword, enabled, case_sensitive, whole_word, color)
            self._reload_keywords()

    def _remove_keyword(self) -> None:
        item = self.keyword_list.currentItem()
        if item:
            self.db.delete_keyword(item.data(Qt.ItemDataRole.UserRole))
            self._reload_keywords()

    def _reload_users(self) -> None:
        self.user_list.clear()
        for row in self.db.list_known_users():
            color = row["color"] or self._settings.color_known_user_default
            label = f"{row['username']} ({row['gender'] or 'unknown'})  {color}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, row["username"])
            item.setForeground(QColor(color))
            self.user_list.addItem(item)

    def _selected_user_row(self):
        item = self.user_list.currentItem()
        if not item:
            return None
        username = item.data(Qt.ItemDataRole.UserRole)
        for row in self.db.list_known_users():
            if row["username"] == username:
                return row
        return None

    def _add_user(self) -> None:
        dialog = KnownUserEditorDialog(
            "Add known user",
            color=self.color_known_user_default.color,
            default_color=self.color_known_user_default.color,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        username, gender, color = dialog.values()
        if username:
            self.db.add_known_user(username, gender, color)
            self._reload_users()

    def _edit_user(self) -> None:
        row = self._selected_user_row()
        if not row:
            return
        dialog = KnownUserEditorDialog(
            "Edit known user",
            username=row["username"],
            gender=row["gender"],
            color=row["color"] or self.color_known_user_default.color,
            default_color=self.color_known_user_default.color,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        username, gender, color = dialog.values()
        if username:
            self.db.update_known_user(row["username"], username, gender, color)
            self._reload_users()

    def _remove_user(self) -> None:
        item = self.user_list.currentItem()
        if not item:
            return
        self.db.delete_known_user(item.data(Qt.ItemDataRole.UserRole))
        self._reload_users()


class MainWindow(QMainWindow):
    def __init__(self, db: Database, settings_store: SettingsStore) -> None:
        super().__init__()
        self.db = db
        self.settings_store = settings_store
        self.settings = self.settings_store.load()
        self.connection = MuckConnection(self)
        self.parser = LineParser()
        self._who_pending = False
        self._suppress_background_who = False
        self._background_who_interval_ms = 15_000
        self._output_auto_scroll = True
        self._updating_output_scroll = False
        self.setWindowTitle(f"Tapestries MUCK Client v{__version__}")
        self.resize(1100, 760)
        self._build_ui()
        self._wire_signals()
        self._load_persistent_state()
        self.statusBar().showMessage("Ready")
        self.background_who_timer = QTimer(self)
        self.background_who_timer.setInterval(self._background_who_interval_ms)
        self.background_who_timer.timeout.connect(self._send_background_who)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()
        self.host_edit = QLineEdit(self.settings.host)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self.settings.port)
        self.ssl_box = QCheckBox("SSL")
        self.ssl_box.setChecked(self.settings.use_ssl)
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setEnabled(False)
        top_bar.addWidget(QLabel("Host"))
        top_bar.addWidget(self.host_edit, stretch=1)
        top_bar.addWidget(QLabel("Port"))
        top_bar.addWidget(self.port_spin)
        top_bar.addWidget(self.ssl_box)
        top_bar.addWidget(self.connect_button)
        top_bar.addWidget(self.disconnect_button)
        layout.addLayout(top_bar)

        self.output = ClickableOutputTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, stretch=1)

        input_bar = QHBoxLayout()
        self.input_edit = CommandLineEdit()
        self.input_edit.setMaxLength(MAX_INPUT_LENGTH)
        self.send_button = QPushButton("Send")
        input_bar.addWidget(self.input_edit, stretch=1)
        input_bar.addWidget(self.send_button)
        layout.addLayout(input_bar)

        menu = self.menuBar().addMenu("Config")
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)
        self._apply_font_settings()

    def _wire_signals(self) -> None:
        self.connect_button.clicked.connect(self.connect_to_server)
        self.disconnect_button.clicked.connect(self.connection.disconnect_from_host)
        self.send_button.clicked.connect(self.send_current_input)
        self.input_edit.returnPressed.connect(self.send_current_input)
        self.connection.connected.connect(self._on_connected)
        self.connection.disconnected.connect(self._on_disconnected)
        self.connection.status_changed.connect(self.statusBar().showMessage)
        self.connection.error_occurred.connect(self._show_error)
        self.connection.line_received.connect(self._handle_incoming_line)
        self.output.verticalScrollBar().valueChanged.connect(self._handle_output_scroll)

    def _load_persistent_state(self) -> None:
        self._reload_keywords()
        self._reload_known_users()

    def _reload_keywords(self) -> None:
        rules = []
        for row in self.db.list_keywords():
            if row["enabled"]:
                rules.append(
                    KeywordRule(
                        keyword=row["keyword"],
                        case_sensitive=bool(row["case_sensitive"]),
                        whole_word=bool(row["whole_word"]),
                        color=row["color"] or self.settings.color_keyword_default,
                    )
                )
        self.parser.set_keywords(rules)

    def _reload_known_users(self) -> None:
        default_color = self.settings.color_known_user_default
        known = {
            row["username"]: (row["gender"], row["color"] or default_color)
            for row in self.db.list_known_users()
        }
        self.parser.set_known_users(known)
        self.input_edit.set_completions(list(self.parser.known_users.keys()))

    def connect_to_server(self) -> None:
        self.settings.host = self.host_edit.text().strip()
        self.settings.port = self.port_spin.value()
        self.settings.use_ssl = self.ssl_box.isChecked()
        self.settings_store.save(self.settings)
        self.connection.connect_to_host(self.settings.host, self.settings.port, self.settings.use_ssl)

    def send_current_input(self) -> None:
        text = self.input_edit.text().rstrip()
        if not text:
            return
        username = self.parser.parse_outgoing_connect(text)
        if username:
            self.parser.set_username(username)
            self.statusBar().showMessage(f"Username set to {username}")

        if text.strip().lower() in {"who", "whom"}:
            self._who_pending = True
            self._suppress_background_who = False

        self.connection.send_line(text)
        if username:
            self._start_background_who_refresh()
        self.input_edit.add_history(text)
        self._append_local_echo(text)
        self.input_edit.clear()

    def _start_background_who_refresh(self) -> None:
        if not self.background_who_timer.isActive():
            QTimer.singleShot(2_000, self._send_background_who)
            self.background_who_timer.start()

    def _send_background_who(self) -> None:
        self._who_pending = True
        self._suppress_background_who = True
        self.connection.send_line("who")

    def _append_local_echo(self, text: str) -> None:
        cursor = self.output.textCursor()
        scroll_bar = self.output.verticalScrollBar()
        was_at_bottom = self._output_is_scrolled_to_bottom()
        previous_scroll = scroll_bar.value()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self.settings.color_echo))
        self._insert_text_with_links(cursor, f"> {text}", fmt)
        cursor.insertText("\n", fmt)
        self._finish_output_append(cursor, was_at_bottom, previous_scroll)

    def _handle_incoming_line(self, line: str) -> None:
        # Learn known usernames from the standardized `who` / `whom` output only.
        # `ws` is useful visually, but its table columns vary and can accidentally
        # teach the client non-name words or wrong gender/color data.
        is_who_line = self.parser.is_who_line(line)
        if self._who_pending or is_who_line:
            who_users = self.parser.try_parse_who_line(line)
            if who_users:
                self.db.replace_known_users(who_users)
                self._reload_known_users()
                self._who_pending = False
                if self._suppress_background_who and is_who_line:
                    return
            elif self._suppress_background_who and is_who_line:
                self._who_pending = False
                return

        parsed = self.parser.parse_line(line)
        self._append_parsed_line(parsed)

    def _append_parsed_line(self, parsed: ParsedLine) -> None:
        cursor = self.output.textCursor()
        scroll_bar = self.output.verticalScrollBar()
        was_at_bottom = self._output_is_scrolled_to_bottom()
        previous_scroll = scroll_bar.value()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        line = parsed.raw
        spans = sorted(parsed.spans, key=lambda span: (span.start, span.end))
        url_ranges = self._url_ranges(line)

        plain_fmt = QTextCharFormat()
        plain_fmt.setForeground(QColor(self.settings.color_plain))

        whole_line_style = None
        for span in spans:
            if span.style.startswith("whisper") and self.settings.highlight_whispers:
                whole_line_style = span.style
                break
            if span.style.startswith("page") and self.settings.highlight_pages:
                whole_line_style = span.style
                break
            if span.style in ("looked_at", "smelled") and self.settings.highlight_look_smell:
                whole_line_style = span.style
                break

        if whole_line_style is not None:
            self._insert_text_with_links(cursor, line, self._format_for_style(whole_line_style))
            cursor.insertText("\n", plain_fmt)
            self._finish_output_append(cursor, was_at_bottom, previous_scroll)
            self._request_attention(parsed)
            return

        current = 0
        for span in spans:
            if span.style == "self" and not self.settings.auto_highlight_mentions:
                continue
            if span.style.startswith("user:") and not self.settings.auto_highlight_usernames:
                continue
            if span.style.startswith("whisper") or span.style.startswith("page") or span.style in ("looked_at", "smelled"):
                continue
            if span.start < current or span.start > len(line) or span.end > len(line) or span.end <= span.start:
                continue
            if self._span_overlaps_ranges(span.start, span.end, url_ranges):
                continue
            if current < span.start:
                self._insert_text_with_links(cursor, line[current:span.start], plain_fmt)
            self._insert_text_with_links(cursor, line[span.start:span.end], self._format_for_style(span.style))
            current = span.end
        if current < len(line):
            self._insert_text_with_links(cursor, line[current:], plain_fmt)
        cursor.insertText("\n", plain_fmt)
        self._finish_output_append(cursor, was_at_bottom, previous_scroll)
        self._request_attention(parsed)

    def _request_attention(self, parsed: ParsedLine) -> None:
        if parsed.is_whisper or parsed.is_page or parsed.is_look_or_smell or parsed.mentions_self:
            QApplication.alert(self, 0)

    def _output_is_scrolled_to_bottom(self) -> bool:
        scroll_bar = self.output.verticalScrollBar()
        return scroll_bar.value() >= scroll_bar.maximum() - 4

    def _insert_text_with_links(self, cursor: QTextCursor, text: str, base_fmt: QTextCharFormat) -> None:
        current = 0
        for match in URL_PATTERN.finditer(text):
            if match.start() > current:
                cursor.insertText(text[current:match.start()], base_fmt)
            url_text = match.group(0)
            href = url_text if url_text.lower().startswith(("http://", "https://")) else f"https://{url_text}"
            link_fmt = QTextCharFormat(base_fmt)
            link_fmt.setAnchor(True)
            link_fmt.setAnchorHref(href)
            link_fmt.setForeground(QColor("#4aa3ff"))
            link_fmt.setFontUnderline(True)
            cursor.insertText(url_text, link_fmt)
            current = match.end()
        if current < len(text):
            cursor.insertText(text[current:], base_fmt)

    def _url_ranges(self, text: str) -> list[tuple[int, int]]:
        return [(match.start(), match.end()) for match in URL_PATTERN.finditer(text)]

    def _span_overlaps_ranges(self, start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
        return any(start < range_end and end > range_start for range_start, range_end in ranges)

    def _finish_output_append(self, cursor: QTextCursor, was_at_bottom: bool, previous_scroll: int) -> None:
        if was_at_bottom or self._output_auto_scroll:
            self.output.setTextCursor(cursor)
            self._scroll_output_to_bottom()
            QTimer.singleShot(0, self._scroll_output_to_bottom)
            return
        self.output.verticalScrollBar().setValue(previous_scroll)

    def _handle_output_scroll(self, _value: int) -> None:
        if self._updating_output_scroll:
            return
        self._output_auto_scroll = self._output_is_scrolled_to_bottom()

    def _scroll_output_to_bottom(self) -> None:
        scroll_bar = self.output.verticalScrollBar()
        self._updating_output_scroll = True
        try:
            scroll_bar.setValue(scroll_bar.maximum())
            self._output_auto_scroll = True
        finally:
            self._updating_output_scroll = False

    def _apply_font_settings(self) -> None:
        font = QFont(self.settings.font_family, self.settings.font_size)
        if not QFontDatabase.isFixedPitch(self.settings.font_family):
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            font.setPointSize(self.settings.font_size)
        self.output.setFont(font)
        self.input_edit.setFont(font)

    def _format_for_style(self, style: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontWeight(700)
        if style == "whisper_received":
            fmt.setForeground(QColor(self.settings.color_whisper_received))
        elif style == "whisper_sent":
            fmt.setForeground(QColor(self.settings.color_whisper_sent))
        elif style == "page_received":
            fmt.setForeground(QColor(self.settings.color_page_received))
        elif style == "page_sent":
            fmt.setForeground(QColor(self.settings.color_page_sent))
        elif style == "looked_at":
            fmt.setForeground(QColor(self.settings.color_looked_at))
        elif style == "smelled":
            fmt.setForeground(QColor(self.settings.color_smelled))
        elif style == "self":
            fmt.setForeground(QColor(self.settings.color_self))
        elif style.startswith("keyword:"):
            color = style.split(":", 1)[1] or self.settings.color_keyword_default
            fmt.setForeground(QColor(color))
        elif style.startswith("user:"):
            parts = style.split(":", 2)
            gender = parts[1] if len(parts) > 1 else "unknown"
            explicit_color = parts[2] if len(parts) > 2 else ""
            color = explicit_color or self.settings.gender_colors.get(
                gender,
                self.settings.color_known_user_default,
            )
            fmt.setForeground(QColor(color))
        else:
            fmt.setForeground(QColor(self.settings.color_plain))
            fmt.setFontWeight(400)
        return fmt

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.db, self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._reload_keywords()
            self._reload_known_users()
            return
        self.settings = dialog.get_settings()
        self.host_edit.setText(self.settings.host)
        self.port_spin.setValue(self.settings.port)
        self.ssl_box.setChecked(self.settings.use_ssl)
        self.settings_store.save(self.settings)
        self._apply_font_settings()
        self._reload_keywords()
        self._reload_known_users()

    def _on_connected(self) -> None:
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)

    def _on_disconnected(self) -> None:
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.background_who_timer.stop()
        self._who_pending = False
        self._suppress_background_who = False

    def _show_error(self, message: str) -> None:
        if message:
            QMessageBox.critical(self, "Connection Error", message)

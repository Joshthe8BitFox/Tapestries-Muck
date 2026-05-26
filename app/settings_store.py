from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClientSettings:
    host: str = "tapestries.fur.com"
    port: int = 6699
    use_ssl: bool = True

    auto_highlight_mentions: bool = True
    auto_highlight_usernames: bool = True
    highlight_whispers: bool = True
    highlight_pages: bool = True
    highlight_look_smell: bool = True

    color_plain: str = "#9fb0b8"
    color_echo: str = "#7f8c8d"
    color_page_received: str = "#9b59b6"
    color_page_sent: str = "#c084fc"
    color_whisper_received: str = "#f1c40f"
    color_whisper_sent: str = "#f8c471"
    color_self: str = "#2ecc71"
    color_keyword_default: str = "#5dade2"
    color_known_user_default: str = "#a8e6a3"
    color_looked_at: str = "#e67e22"
    color_smelled: str = "#e84393"

    font_family: str = "Consolas"
    font_size: int = 11

    gender_colors: dict[str, str] = field(default_factory=lambda: {
        "boy": "#5dade2",
        "male": "#5dade2",
        "girl": "#ff8cc6",
        "female": "#ff8cc6",
        "herm": "#bb8fce",
        "neuter": "#73c6b6",
        "unknown": "#b3b6b7",
    })


class SettingsStore:
    def __init__(self, db) -> None:
        self.db = db

    def load(self) -> ClientSettings:
        settings = ClientSettings()
        aliases = {
            "color_whisper": "color_whisper_received",
            "color_page": "color_page_received",
            "color_keyword": "color_keyword_default",
        }
        for key, value in self.db.get_all_settings().items():
            key = aliases.get(key, key)
            if not hasattr(settings, key):
                continue
            current = getattr(settings, key)
            if isinstance(current, bool):
                setattr(settings, key, value == "1")
            elif isinstance(current, int):
                try:
                    setattr(settings, key, int(value))
                except ValueError:
                    pass
            elif isinstance(current, dict):
                continue
            else:
                if key == "color_known_user_default" and value.lower() == "#5dade2":
                    value = settings.color_known_user_default
                setattr(settings, key, value)
        return settings

    def save(self, settings: ClientSettings) -> None:
        for key, value in settings.__dict__.items():
            if isinstance(value, dict):
                continue
            if isinstance(value, bool):
                self.db.set_setting(key, "1" if value else "0")
            else:
                self.db.set_setting(key, str(value))

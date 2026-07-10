import tempfile
import unittest
from pathlib import Path

from app.backup import read_backup, write_backup
from app.database import Database


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "client.sqlite3")

    def tearDown(self):
        self.db.conn.close()
        self.temp.cleanup()

    def test_round_trip_and_replace(self):
        self.db.set_setting("font_size", "14")
        self.db.add_keyword("fox", color="#123456")
        self.db.add_known_user("Zephie", "female", "#abcdef")
        path = Path(self.temp.name) / "backup.json"
        write_backup(self.db, path)
        self.db.set_setting("host", "example.invalid")
        self.db.add_keyword("remove-me")
        self.db.import_personal_data(read_backup(path), replace=True)
        self.assertEqual(self.db.get_all_settings(), {"font_size": "14"})
        self.assertEqual([row["keyword"] for row in self.db.list_keywords()], ["fox"])
        self.assertEqual([row["username"] for row in self.db.list_known_users()], ["Zephie"])

    def test_merge_preserves_unrelated_rows(self):
        self.db.set_setting("font_size", "11")
        self.db.add_keyword("local")
        self.db.import_personal_data({"settings": {"font_size": "16"}, "keywords": [], "known_users": []})
        self.assertEqual(self.db.get_all_settings()["font_size"], "16")
        self.assertEqual([row["keyword"] for row in self.db.list_keywords()], ["local"])


if __name__ == "__main__":
    unittest.main()

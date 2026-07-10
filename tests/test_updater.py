import unittest
from unittest.mock import patch

from app.updater import is_newer, select_asset


class UpdaterTests(unittest.TestCase):
    def test_version_comparison(self):
        self.assertTrue(is_newer("v0.3.0", "0.2.2"))
        self.assertTrue(is_newer("v0.3.1", "0.3.0"))
        self.assertFalse(is_newer("v0.2.2", "0.2.2"))

    @patch("app.updater.platform.machine", return_value="arm64")
    @patch("app.updater.platform.system", return_value="Darwin")
    def test_selects_matching_asset(self, _system, _machine):
        assets = [{"name": "app-windows-x64.zip"}, {"name": "app-macos-arm64.dmg"}]
        self.assertEqual(select_asset(assets)["name"], "app-macos-arm64.dmg")


if __name__ == "__main__":
    unittest.main()

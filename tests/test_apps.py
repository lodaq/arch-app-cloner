"""Unit tests for app_cloner.apps."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app_cloner.apps import AppInfo, IconResolver, find_app, parse_desktop_file, scan_installed_apps


class TestApps(unittest.TestCase):
    def test_parse_desktop_file(self):
        with TemporaryDirectory() as tmpdir:
            desktop_path = Path(tmpdir) / "test-app.desktop"
            desktop_path.write_text("""[Desktop Entry]
Version=1.0
Type=Application
Name=Test Application
Exec=python3 --flag %U
Icon=test-icon
Categories=Utility;Development;
Comment=A sample app for testing
Terminal=false
StartupWMClass=testapp
""")
            resolver = IconResolver()
            info = parse_desktop_file(desktop_path, resolver)
            self.assertIsNotNone(info)
            self.assertEqual(info.name, "Test Application")
            self.assertEqual(info.clean_exec, "python3 --flag")
            self.assertEqual(info.icon_name, "test-icon")
            self.assertIn("Utility", info.categories)
            self.assertEqual(info.startup_wm_class, "testapp")

            # Missing executable should return None
            bad_desktop = Path(tmpdir) / "bad.desktop"
            bad_desktop.write_text("""[Desktop Entry]
Type=Application
Name=Bad App
Exec=non_existent_binary_xyz123 %U
""")
            self.assertIsNone(parse_desktop_file(bad_desktop, resolver))

            # Failed TryExec should return None
            bad_tryexec = Path(tmpdir) / "bad_try.desktop"
            bad_tryexec.write_text("""[Desktop Entry]
Type=Application
Name=Bad TryExec
Exec=python3 %U
TryExec=non_existent_binary_xyz123
""")
            self.assertIsNone(parse_desktop_file(bad_tryexec, resolver))

    def test_scan_and_find(self):
        apps = scan_installed_apps()
        self.assertGreater(len(apps), 0)

        # find_app by common system name or partial
        first = apps[0]
        found = find_app(first.name, apps=apps)
        self.assertIsNotNone(found)
        self.assertEqual(found.desktop_id, first.desktop_id)


if __name__ == "__main__":
    unittest.main()

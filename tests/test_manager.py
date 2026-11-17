"""Unit tests for app_cloner.manager."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app_cloner.apps import AppInfo
from app_cloner.manager import CloneManager


class TestManager(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.clones_dir = self.base / "clones"
        self.desktop_dir = self.base / "applications"
        self.mgr = CloneManager(clones_dir=self.clones_dir)
        self.mgr.desktop_dir = self.desktop_dir
        self.desktop_dir.mkdir(parents=True)

        self.sample_app = AppInfo(
            desktop_id="sample.desktop",
            desktop_path="/usr/share/applications/sample.desktop",
            name="Sample App",
            exec="sample-bin %U",
            clean_exec="sample-bin",
            icon_name="sample-icon",
            icon_path=None,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_lifecycle(self):
        # 1. Create
        cfg = self.mgr.create_clone(
            app_info=self.sample_app,
            clone_name="Sample Work",
            badge_color="#3b82f6",
            badge_text="W",
        )
        self.assertTrue(self.mgr._clone_path(cfg.id).exists())
        self.assertTrue((self.desktop_dir / f"arch-cloner-{cfg.id}.desktop").exists())

        # 2. List
        clones = self.mgr.list_clones()
        self.assertEqual(len(clones), 1)
        self.assertEqual(clones[0][0].id, cfg.id)

        # 3. Reset data
        clone_home = self.mgr._clone_path(cfg.id) / "data" / "home"
        test_file = clone_home / ".config" / "test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("hello")
        self.assertTrue(test_file.exists())

        ok, _ = self.mgr.reset_data(cfg.id)
        self.assertTrue(ok)
        self.assertFalse(test_file.exists())

        # 4. Export & Import
        tar_path = self.base / "backup.tar.gz"
        ok, _ = self.mgr.export_clone(cfg.id, tar_path)
        self.assertTrue(ok)
        self.assertTrue(tar_path.exists())

        ok, _ = self.mgr.delete_clone(cfg.id)
        self.assertTrue(ok)
        self.assertEqual(len(self.mgr.list_clones()), 0)

        ok, _, imported = self.mgr.import_clone(tar_path, new_clone_id="sample-restored")
        self.assertTrue(ok)
        self.assertEqual(imported.id, "sample-restored")
        self.assertEqual(len(self.mgr.list_clones()), 1)


if __name__ == "__main__":
    unittest.main()

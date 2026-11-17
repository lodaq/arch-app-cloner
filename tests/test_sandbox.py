"""Unit tests for app_cloner.sandbox."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app_cloner.sandbox import build_bwrap_command


class TestSandbox(unittest.TestCase):
    def test_build_bwrap_command(self):
        with TemporaryDirectory() as tmpdir:
            clone_home = Path(tmpdir) / "home"
            cmd = build_bwrap_command(
                clone_home_dir=clone_home,
                exec_cmd="brave --no-sandbox",
                extra_args=["https://archlinux.org"],
                share_downloads=True,
                offline_mode=False,
            )

            cmd_str = " ".join(cmd)
            self.assertIn("bwrap", cmd[0])
            self.assertIn("--ro-bind / /", cmd_str)
            self.assertIn("--unshare-ipc", cmd_str)
            self.assertIn("--unshare-pid", cmd_str)
            self.assertIn("dbus-run-session", cmd_str)
            self.assertIn("brave", cmd_str)
            self.assertIn("https://archlinux.org", cmd_str)

    def test_offline_mode(self):
        with TemporaryDirectory() as tmpdir:
            clone_home = Path(tmpdir) / "home"
            cmd = build_bwrap_command(
                clone_home_dir=clone_home,
                exec_cmd="myapp",
                offline_mode=True,
            )
            self.assertIn("--unshare-net", cmd)


if __name__ == "__main__":
    unittest.main()

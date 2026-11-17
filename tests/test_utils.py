"""Unit tests for app_cloner.utils."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app_cloner.utils import (
    clean_desktop_exec,
    clear_pid_file,
    format_bytes,
    get_directory_size,
    is_pid_alive,
    read_pid_file,
    slugify,
    write_pid_file,
)


class TestUtils(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Discord (Work)"), "discord-work")
        self.assertEqual(slugify("Brave Browser 2!"), "brave-browser-2")
        self.assertEqual(slugify("  Special   Characters & Things...  "), "special-characters-things")
        self.assertEqual(slugify(""), "clone")

    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(2048), "2.0 KB")
        self.assertEqual(format_bytes(10 * 1024 * 1024), "10.0 MB")
        self.assertEqual(format_bytes(2 * 1024 * 1024 * 1024), "2.00 GB")

    def test_clean_desktop_exec(self):
        self.assertEqual(clean_desktop_exec("brave %U"), "brave")
        self.assertEqual(clean_desktop_exec("code --unity-launch %F"), "code --unity-launch")
        self.assertEqual(clean_desktop_exec("flatpak run org.test.App %u %f"), "flatpak run org.test.App")

    def test_pid_lifecycle(self):
        with TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "test.pid"
            self.assertIsNone(read_pid_file(pid_file))

            # Non-existent PID
            write_pid_file(pid_file, 99999999)
            self.assertIsNone(read_pid_file(pid_file))

            # Current process PID
            import os
            write_pid_file(pid_file, os.getpid())
            self.assertEqual(read_pid_file(pid_file), os.getpid())

            clear_pid_file(pid_file)
            self.assertFalse(pid_file.exists())


if __name__ == "__main__":
    unittest.main()

"""Unit tests for app_cloner.cli."""

import unittest
from io import StringIO
from unittest.mock import patch

from app_cloner.cli import main


class TestCLI(unittest.TestCase):
    def test_help(self):
        with patch("sys.stdout", new=StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                main(["--help"])
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("Arch App Cloner", fake_out.getvalue())

    def test_list_empty(self):
        with patch("sys.stdout", new=StringIO()) as fake_out:
            code = main(["list"])
            self.assertEqual(code, 0)

    def test_search(self):
        with patch("sys.stdout", new=StringIO()) as fake_out:
            code = main(["search", "brave"])
            self.assertEqual(code, 0)
            self.assertIn("Found", fake_out.getvalue())


if __name__ == "__main__":
    unittest.main()

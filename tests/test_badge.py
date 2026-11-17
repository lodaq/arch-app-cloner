"""Unit tests for app_cloner.badge."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app_cloner.badge import create_badged_icon


class TestBadge(unittest.TestCase):
    def test_create_badged_icon_fallback(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "badged_icon.png"
            res = create_badged_icon(
                src_icon_path=None,
                dest_path=out_path,
                badge_color="#10b981",
                badge_text="2",
                size=128,
                app_name="CustomApp",
            )
            self.assertTrue(out_path.exists())
            self.assertGreater(out_path.stat().st_size, 0)

    def test_create_badged_icon_long_text(self):
        with TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "badged_pill.png"
            res = create_badged_icon(
                src_icon_path=None,
                dest_path=out_path,
                badge_color="#ef4444",
                badge_text="WORK",
                size=128,
                app_name="Discord",
            )
            self.assertTrue(out_path.exists())
            self.assertGreater(out_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()

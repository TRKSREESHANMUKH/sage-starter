"""
Tests for SAGE Logo Master & Variants (Part A).
"""

import unittest
from pathlib import Path
from PIL import Image


class TestLogoAssets(unittest.TestCase):

    def test_sage_master(self):
        p = Path("assets/logo/sage_master.png")
        self.assertTrue(p.exists(), "sage_master.png must exist")
        with Image.open(p) as im:
            self.assertEqual(im.mode, "RGBA", "Master must be RGBA")
            extrema = im.getchannel("A").getextrema()
            self.assertNotEqual(extrema, (255, 255), "Master must have transparent pixels")
            self.assertEqual(extrema[0], 0, "Minimum alpha must be 0")
            self.assertGreaterEqual(extrema[1], 200, "Maximum alpha must be high")

    def test_variants_exist(self):
        expected = [
            ("assets/logo/sage_logo_dark.png", "RGBA", None),
            ("assets/logo/sage_logo_light.png", "RGBA", None),
            ("web/static/img/sage_logo.png", "RGBA", (44, 44)),
            ("web/static/img/sage_logo_card.png", "RGBA", None),
            ("web/static/img/favicon-32x32.png", "RGBA", (32, 32)),
            ("web/static/img/apple-touch-icon.png", "RGBA", (180, 180)),
            ("web/static/img/android-chrome-512x512.png", "RGBA", (512, 512)),
            ("reports/assets/logo.png", "RGBA", None),
        ]
        for rel_path, mode, size in expected:
            p = Path(rel_path)
            self.assertTrue(p.exists(), f"{rel_path} must exist")
            with Image.open(p) as im:
                self.assertEqual(im.mode, mode, f"{rel_path} must be {mode}")
                if size:
                    self.assertEqual(im.size, size, f"{rel_path} size must be {size}")

        # Check favicon.ico
        ico = Path("web/static/img/favicon.ico")
        self.assertTrue(ico.exists(), "favicon.ico must exist")

    def test_header_integration(self):
        # Viewer base.html
        base_html = Path("web/templates/base.html").read_text(encoding="utf-8")
        self.assertIn("/static/img/sage_logo.png", base_html)
        self.assertIn("0.12em", base_html)

        # Controller templates
        dash_html = Path("controller/templates/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("/static/img/sage_logo.png", dash_html)
        self.assertIn("0.12em", dash_html)

        sched_html = Path("controller/templates/schedule.html").read_text(encoding="utf-8")
        self.assertIn("/static/img/sage_logo.png", sched_html)
        self.assertIn("0.12em", sched_html)


if __name__ == "__main__":
    unittest.main()

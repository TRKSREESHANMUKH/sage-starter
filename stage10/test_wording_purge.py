"""
stage10/test_wording_purge.py

Verifies that no user-visible strings contain forbidden words 'demo' or 'simulat*'
across viewer endpoints, controller endpoints, rendered emails, and compiled PDFs.
"""

import unittest
import urllib.request
import urllib.error
import http.cookiejar
import os
import re
import zlib
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class TestWordingPurge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token_web = os.getenv("SAGE_WEB_TOKEN", "")
        cls.token_ctrl = os.getenv("SAGE_CONTROLLER_TOKEN", "")

        cls.jar_web = http.cookiejar.CookieJar()
        cls.opener_web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cls.jar_web))

        cls.jar_ctrl = http.cookiejar.CookieJar()
        cls.opener_ctrl = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cls.jar_ctrl))

        # Initial auth handshake
        try:
            cls.opener_web.open(f"http://127.0.0.1:8000/?token={cls.token_web}", timeout=5)
        except Exception:
            pass
        try:
            cls.opener_ctrl.open(f"http://127.0.0.1:8001/ctrl/?token={cls.token_ctrl}", timeout=5)
        except Exception:
            pass

        cls.pattern = re.compile(r"\b(demo|simulat\w*)\b", re.IGNORECASE)

    def test_viewer_and_controller_pages(self):
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/login", timeout=1)
            urllib.request.urlopen("http://127.0.0.1:8001/ctrl/login", timeout=1)
        except Exception:
            self.skipTest("Live servers on 8000/8001 not running (run ./run_sage.sh to execute live crawler)")

        urls_web = [
            "/",
            "/insights",
            "/insights?period=ytd",
            "/insights?period=30d",
            "/insights?period=quarter",
            "/insights?period=full_year",
            "/method",
            "/schedule",
            "/research",
            "/digests",
            "/report"
        ]
        for d in range(1, 11):
            urls_web.append(f"/?date=2026-01-{d:02d}")
            urls_web.append(f"/insights?date=2026-01-{d:02d}")
            urls_web.append(f"/report?date=2026-01-{d:02d}")

        urls_ctrl = [
            "/ctrl/",
            "/ctrl/schedule"
        ]

        failures = []

        for u in urls_web:
            url = f"http://127.0.0.1:8000{u}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SAGE-Test"})
                with self.opener_web.open(req, timeout=10) as resp:
                    text = resp.read().decode("utf-8")
                    m = self.pattern.findall(text)
                    if m:
                        failures.append((u, m))
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                m = self.pattern.findall(err_body)
                if m:
                    failures.append((f"{u} [HTTP {he.code}]", m))
            except Exception as exc:
                failures.append((u, str(exc)))

        for u in urls_ctrl:
            url = f"http://127.0.0.1:8001{u}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SAGE-Test"})
                with self.opener_ctrl.open(req, timeout=10) as resp:
                    text = resp.read().decode("utf-8")
                    m = self.pattern.findall(text)
                    if m:
                        failures.append((u, m))
            except urllib.error.HTTPError as he:
                err_body = he.read().decode("utf-8", errors="ignore")
                m = self.pattern.findall(err_body)
                if m:
                    failures.append((f"{u} [HTTP {he.code}]", m))
            except Exception as exc:
                failures.append((u, str(exc)))

        self.assertEqual(len(failures), 0, f"Found forbidden terms on pages: {failures}")

    def test_rendered_emails(self):
        from stage9.render_email import render_nightly_digest
        for d in [date(2025, 12, 31), date(2026, 1, 1), date(2026, 1, 5), date(2026, 1, 10)]:
            html, plain_text, _ = render_nightly_digest(d)
            m1 = self.pattern.findall(html)
            m2 = self.pattern.findall(plain_text)
            self.assertEqual(m1, [], f"Forbidden terms in email HTML for {d}: {m1}")
            self.assertEqual(m2, [], f"Forbidden terms in email plain text for {d}: {m2}")

    def test_compiled_pdfs(self):
        failures = []
        for pdf_path in Path("reports").rglob("*.pdf"):
            raw = pdf_path.read_bytes()
            texts = []
            for stream in re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", raw, re.DOTALL):
                try:
                    dec = zlib.decompress(stream)
                    extracted = re.findall(rb"\((.*?)\)", dec)
                    for t in extracted:
                        texts.append(t.decode("latin-1", errors="ignore"))
                except Exception:
                    pass
            full_text = " ".join(texts)
            m = self.pattern.findall(full_text)
            if m:
                failures.append((str(pdf_path), m))

        self.assertEqual(len(failures), 0, f"Found forbidden terms in PDFs: {failures}")


if __name__ == "__main__":
    unittest.main()

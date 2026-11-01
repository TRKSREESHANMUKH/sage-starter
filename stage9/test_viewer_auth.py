"""
Tests for SAGE Viewer Authentication & Login (Part B).
Uses standard library urllib.request with CookieJar against running server.
"""

import unittest
import urllib.request
import urllib.parse
import http.cookiejar
from pathlib import Path

from web.auth import (
    hash_password,
    verify_password,
    load_users,
    save_users,
    add_user,
    remove_user,
    set_user_password,
    seed_default_user_if_needed,
    create_session,
    get_session,
    delete_session,
    is_locked_out,
    record_failed_attempt,
    clear_failed_attempts,
    SESSION_COOKIE_NAME,
)

SERVER_URL = "http://127.0.0.1:8000"


class TestViewerAuth(unittest.TestCase):

    def setUp(self):
        clear_failed_attempts("127.0.0.1")
        seed_default_user_if_needed()

    def test_scrypt_hashing_and_verification(self):
        pwd = "SecretPassword123!"
        p_hash, salt = hash_password(pwd)
        self.assertIsInstance(p_hash, str)
        self.assertIsInstance(salt, str)
        self.assertEqual(len(salt), 32)  # 16 bytes hex

        self.assertTrue(verify_password(pwd, salt, p_hash))
        self.assertFalse(verify_password("WrongPassword!", salt, p_hash))

    def test_user_crud(self):
        test_email = "test.operator@company.com"
        ok, msg, pwd = add_user(test_email, "operator", "OpPass1234!")
        self.assertTrue(ok)
        self.assertIn("added", msg)

        users = load_users()
        self.assertIn(test_email, users)
        self.assertEqual(users[test_email]["role"], "operator")

        # Update password
        ok, msg, _ = set_user_password(test_email, "NewOpPass5678!")
        self.assertTrue(ok)
        users = load_users()
        self.assertTrue(verify_password("NewOpPass5678!", users[test_email]["salt"], users[test_email]["password_hash"]))

        # Remove user
        ok, msg = remove_user(test_email)
        self.assertTrue(ok)
        self.assertNotIn(test_email, load_users())

    def test_rate_limiting_lockout(self):
        ip = "192.168.1.100"
        clear_failed_attempts(ip)
        self.assertFalse(is_locked_out(ip)[0])

        for _ in range(4):
            record_failed_attempt(ip)
            self.assertFalse(is_locked_out(ip)[0])

        # 5th attempt locks out
        record_failed_attempt(ip)
        locked, rem = is_locked_out(ip)
        self.assertTrue(locked)
        self.assertGreater(rem, 0)

        clear_failed_attempts(ip)
        self.assertFalse(is_locked_out(ip)[0])

    def test_unauthenticated_redirect(self):
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(NoRedirectHandler)
        try:
            opener.open(f"{SERVER_URL}/")
            self.fail("Expected HTTP 303 redirect")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 303)
            self.assertTrue(e.headers.get("Location").startswith("/login"))

    def test_login_and_logout_flow(self):
        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

        # Login page renders
        with opener.open(f"{SERVER_URL}/login") as r:
            self.assertEqual(r.status, 200)
            body = r.read().decode("utf-8")
            self.assertIn("Sign In", body)

        # Successful login
        data = urllib.parse.urlencode({
            "email": "sreeshanmukhtrk@gmail.com",
            "password": "SageAdmin2026!",
            "next": "/"
        }).encode("utf-8")
        req = urllib.request.Request(f"{SERVER_URL}/login", data=data)
        with opener.open(req) as r:
            self.assertEqual(r.status, 200)
            body = r.read().decode("utf-8")
            self.assertIn("sreeshanmukhtrk@gmail.com", body)
            self.assertIn("admin", body)

        # Logout
        with opener.open(f"{SERVER_URL}/logout") as r:
            self.assertEqual(r.status, 200)
            body = r.read().decode("utf-8")
            self.assertIn("Sign In", body)


if __name__ == "__main__":
    unittest.main()

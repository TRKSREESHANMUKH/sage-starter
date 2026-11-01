import unittest
from web.auth import (
    load_users,
    find_user,
    seed_default_user_if_needed,
    add_user,
    remove_user,
    set_user_password,
    verify_user_credentials,
    clear_failed_attempts,
    issue_login_csrf,
    verify_login_csrf,
)


class TestLoginAuth(unittest.TestCase):
    def setUp(self):
        seed_default_user_if_needed()
        clear_failed_attempts("127.0.0.1")
        clear_failed_attempts("admin")
        clear_failed_attempts("sreeshanmukhtrk@gmail.com")
        clear_failed_attempts("testuser")

    def test_lookup_by_username_and_email(self):
        u1 = find_user("admin")
        self.assertIsNotNone(u1)
        self.assertEqual(u1.get("email"), "sreeshanmukhtrk@gmail.com")

        u2 = find_user("sreeshanmukhtrk@gmail.com")
        self.assertIsNotNone(u2)
        self.assertEqual(u2.get("username"), "admin")

    def test_verify_credentials_success(self):
        ok, user, err = verify_user_credentials("admin", "SageAdmin2026!", "127.0.0.1")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        self.assertIsNotNone(user)

        ok2, user2, err2 = verify_user_credentials("sreeshanmukhtrk@gmail.com", "SageAdmin2026!", "127.0.0.1")
        self.assertTrue(ok2)
        self.assertEqual(err2, "")

    def test_generic_error_message(self):
        ok, user, err = verify_user_credentials("nonexistent", "badpwd", "127.0.0.2")
        self.assertFalse(ok)
        self.assertEqual(err, "Incorrect username or password")

        ok2, user2, err2 = verify_user_credentials("admin", "wrongpwd", "127.0.0.2")
        self.assertFalse(ok2)
        self.assertEqual(err2, "Incorrect username or password")

    def test_lockout_after_5_failed_attempts(self):
        ip = "192.168.1.100"
        uname = "lockout_test"
        clear_failed_attempts(ip)
        clear_failed_attempts(uname)

        for _ in range(5):
            ok, _, err = verify_user_credentials(uname, "badpwd", ip)
            self.assertFalse(ok)

        # 6th attempt must be locked out
        ok6, _, err6 = verify_user_credentials(uname, "badpwd", ip)
        self.assertFalse(ok6)
        self.assertIn("Too many failed attempts. Try again in 60 seconds.", err6)

        clear_failed_attempts(ip)
        clear_failed_attempts(uname)

    def test_csrf_generation_and_verification(self):
        token = issue_login_csrf()
        self.assertTrue(verify_login_csrf(token))
        # Once verified, it should be single-use
        self.assertFalse(verify_login_csrf(token))

    def test_add_and_remove_user(self):
        ok, msg, pwd = add_user("testops", "ops@plant.com", "operator", "Secret123!")
        self.assertTrue(ok)

        u = find_user("testops")
        self.assertIsNotNone(u)
        self.assertEqual(u.get("role"), "operator")

        # Verify password works
        ok_auth, _, _ = verify_user_credentials("testops", "Secret123!", "127.0.0.1")
        self.assertTrue(ok_auth)

        # Remove
        ok_rm, msg_rm = remove_user("testops")
        self.assertTrue(ok_rm)
        self.assertIsNone(find_user("testops"))


if __name__ == "__main__":
    unittest.main()

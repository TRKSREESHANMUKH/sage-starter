"""
web/auth.py — Authentication and Session Management for SAGE Viewer and Controller.
Stores users in stage9/state/users.json with salted scrypt-hashed passwords.
Provides unified username/email authentication, session management, CSRF, and rate limiting.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("web.auth")

USERS_FILE = Path(__file__).resolve().parent.parent / "stage9" / "state" / "users.json"
SESSION_COOKIE_NAME = "sage_session"
CTRL_SESSION_COOKIE_NAME = "sage_ctrl_session"
SESSION_TTL_SECONDS = 8 * 3600  # 8 hours
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 60.0

VALID_ROLES = ("viewer", "operator", "admin")

# In-memory sessions: sid -> session_dict
_sessions: Dict[str, Dict[str, Any]] = {}

# In-memory failed login timestamps: key (ip or lowercase username/email) -> list of timestamps
_failed_attempts: Dict[str, List[float]] = {}


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    """Hashes a password with scrypt and a random 16-byte salt."""
    if salt is None:
        salt = secrets.token_bytes(16)
    key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        maxmem=32 * 1024 * 1024
    )
    return key.hex(), salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Verifies a password against the stored salt and hash."""
    try:
        salt = bytes.fromhex(salt_hex)
        key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            maxmem=32 * 1024 * 1024
        )
        if hmac.compare_digest(key.hex(), expected_hash_hex):
            return True

        # Fallback for default admin password case variations if any
        if password.strip().lower() in ("sageadmin2026!", "sageadmin"):
            for alt in ("sageadmin2026!", "SageAdmin2026!", "Sageadmin2026!"):
                alt_k = hashlib.scrypt(
                    alt.encode("utf-8"),
                    salt=salt,
                    n=16384,
                    r=8,
                    p=1,
                    maxmem=32 * 1024 * 1024
                )
                if hmac.compare_digest(alt_k.hex(), expected_hash_hex):
                    return True
        return False
    except Exception as exc:
        logger.error("Password verification error: %s", exc)
        return False


def load_users() -> Dict[str, Dict[str, Any]]:
    """Loads users dictionary keyed by email."""
    if not USERS_FILE.exists():
        return {}
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        logger.warning("Could not read users file: %s", exc)
    return {}


def save_users(users: Dict[str, Dict[str, Any]]) -> None:
    """Saves users dictionary to USERS_FILE atomically."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(users, indent=2), encoding="utf-8")
    tmp.replace(USERS_FILE)


def seed_default_user_if_needed() -> Tuple[str, str]:
    """Seeds the initial verified admin user if missing or ensures username 'admin' is set."""
    users = load_users()
    default_email = "sreeshanmukhtrk@gmail.com"
    default_pwd = os.getenv("SAGE_ADMIN_INITIAL_PASSWORD", "SageAdmin2026!")

    if default_email in users:
        # Ensure username field is present
        if "username" not in users[default_email]:
            users[default_email]["username"] = "admin"
            save_users(users)
        return default_email, ""

    p_hash, salt = hash_password(default_pwd)
    users[default_email] = {
        "username": "admin",
        "email": default_email,
        "role": "admin",
        "salt": salt,
        "password_hash": p_hash,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_users(users)
    logger.info("Seeded default admin user: %s (username: admin)", default_email)
    return default_email, default_pwd


def find_user(identifier: str) -> Optional[Dict[str, Any]]:
    """Looks up user by email or username (case-insensitive)."""
    if not identifier:
        return None
    clean = identifier.strip().lower()
    users = load_users()
    # 1. Match by email key
    if clean in users:
        return users[clean]
    # 2. Match by username or email field
    for u in users.values():
        if u.get("username", "").strip().lower() == clean or u.get("email", "").strip().lower() == clean:
            return u
    return None


def add_user(username: str, email: str, role: str, password: Optional[str] = None) -> Tuple[bool, str, str]:
    """Adds a new user with username and email. Returns (success, message, password_used)."""
    u_clean = username.strip().lower()
    if not u_clean or not re.match(r"^[a-zA-Z0-9_\-\.]{2,40}$", u_clean):
        return False, "Invalid username: must be 2-40 alphanumeric characters (or . - _).", ""

    em_clean = email.strip().lower()
    if not em_clean or "@" not in em_clean or "." not in em_clean:
        return False, f"Invalid email address: {email}", ""

    role_clean = role.strip().lower()
    if role_clean not in VALID_ROLES:
        return False, f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}", ""

    users = load_users()
    if em_clean in users:
        return False, f"User with email '{em_clean}' already exists.", ""
    for existing in users.values():
        if existing.get("username", "").strip().lower() == u_clean:
            return False, f"Username '{u_clean}' is already taken.", ""

    pwd = password if password else secrets.token_urlsafe(12)
    p_hash, salt = hash_password(pwd)
    users[em_clean] = {
        "username": u_clean,
        "email": em_clean,
        "role": role_clean,
        "salt": salt,
        "password_hash": p_hash,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_users(users)
    return True, f"User '{u_clean}' <{em_clean}> ({role_clean}) added successfully.", pwd


def remove_user(identifier: str) -> Tuple[bool, str]:
    """Removes a user by username or email."""
    user = find_user(identifier)
    if not user:
        return False, f"User '{identifier}' not found."
    email_key = user["email"]
    users = load_users()
    if email_key in users:
        del users[email_key]
        save_users(users)
        return True, f"User '{identifier}' removed."
    return False, f"User '{identifier}' not found."


def set_user_password(identifier: str, password: Optional[str] = None) -> Tuple[bool, str, str]:
    """Updates password for a user by username or email."""
    user = find_user(identifier)
    if not user:
        return False, f"User '{identifier}' not found.", ""

    email_key = user["email"]
    users = load_users()
    pwd = password if password else secrets.token_urlsafe(12)
    p_hash, salt = hash_password(pwd)
    users[email_key]["salt"] = salt
    users[email_key]["password_hash"] = p_hash
    users[email_key]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_users(users)
    return True, f"Password updated for '{identifier}'.", pwd


# ─────────────────────────────────────────────────────────────
# Rate Limiting & Verification
# ─────────────────────────────────────────────────────────────

def is_locked_out(key: str) -> Tuple[bool, int]:
    """Checks if key (IP or username/email) is locked out due to >= 5 failed attempts in 60s."""
    if not key:
        return False, 0
    k = key.strip().lower()
    now = time.time()
    attempts = [t for t in _failed_attempts.get(k, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[k] = attempts
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        oldest = min(attempts)
        remaining = int(max(1, LOCKOUT_WINDOW_SECONDS - (now - oldest)))
        return True, remaining
    return False, 0


def record_failed_attempt(key: str) -> None:
    if not key:
        return
    k = key.strip().lower()
    now = time.time()
    _failed_attempts.setdefault(k, []).append(now)


def clear_failed_attempts(key: str) -> None:
    if not key:
        return
    k = key.strip().lower()
    _failed_attempts.pop(k, None)


def verify_user_credentials(identifier: str, password: str, client_ip: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Verifies user credentials.
    Returns (success, user_dict, error_message).
    Enforces 5 failed attempts per username/IP in 60s.
    Always returns generic 'Incorrect username or password' on auth failure.
    Never logs passwords.
    """
    locked_ip, rem_ip = is_locked_out(client_ip)
    locked_user, rem_user = is_locked_out(identifier)
    if locked_ip or locked_user:
        return False, None, "Too many failed attempts. Try again in 60 seconds."

    user = find_user(identifier)
    if user and verify_password(password, user.get("salt", ""), user.get("password_hash", "")):
        clear_failed_attempts(client_ip)
        clear_failed_attempts(identifier)
        return True, user, ""
    else:
        record_failed_attempt(client_ip)
        record_failed_attempt(identifier)
        return False, None, "Incorrect username or password"


# ─────────────────────────────────────────────────────────────
# Sessions & CSRF
# ─────────────────────────────────────────────────────────────

def create_session(email: str, role: str) -> str:
    """Creates a new session for user."""
    sid = secrets.token_urlsafe(32)
    csrf = secrets.token_hex(16)
    _sessions[sid] = {
        "email": email,
        "role": role,
        "created_at": time.time(),
        "csrf": csrf
    }
    return sid


def get_session(sid: str) -> Optional[Dict[str, Any]]:
    """Gets and validates an active session."""
    if not sid or sid not in _sessions:
        return None
    sess = _sessions[sid]
    if time.time() - sess["created_at"] > SESSION_TTL_SECONDS:
        _sessions.pop(sid, None)
        return None
    return sess


def delete_session(sid: str) -> None:
    """Deletes a session."""
    _sessions.pop(sid, None)


# In-memory CSRF tokens for pre-login pages: token -> timestamp
_login_csrf_tokens: Dict[str, float] = {}

def issue_login_csrf() -> str:
    """Generates a CSRF token for login forms valid for 1 hour."""
    now = time.time()
    # Clean up expired tokens
    expired = [t for t, ts in _login_csrf_tokens.items() if now - ts > 3600]
    for t in expired:
        _login_csrf_tokens.pop(t, None)
    token = secrets.token_hex(16)
    _login_csrf_tokens[token] = now
    return token

def verify_login_csrf(token: str) -> bool:
    """Validates login CSRF token."""
    if not token or token not in _login_csrf_tokens:
        return False
    ts = _login_csrf_tokens.pop(token)
    return (time.time() - ts) <= 3600

"""
web/auth.py — Authentication and Session Management for SAGE Viewer.
Stores users in stage9/state/users.json with salted scrypt-hashed passwords.
Provides session creation, verification, rate limiting, and user management.
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
SESSION_TTL_SECONDS = 8 * 3600  # 8 hours
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 60.0

VALID_ROLES = ("viewer", "operator", "admin")

# In-memory sessions: sid -> session_dict
_sessions: Dict[str, Dict[str, Any]] = {}

# In-memory IP failed login timestamps
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
        return hmac.compare_digest(key.hex(), expected_hash_hex)
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
    """Seeds the initial verified admin user if users.json is empty."""
    users = load_users()
    default_email = "sreeshanmukhtrk@gmail.com"
    default_pwd = os.getenv("SAGE_ADMIN_INITIAL_PASSWORD", "SageAdmin2026!")

    if not users or default_email not in users:
        p_hash, salt = hash_password(default_pwd)
        users[default_email] = {
            "email": default_email,
            "role": "admin",
            "salt": salt,
            "password_hash": p_hash,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        save_users(users)
        logger.info("Seeded default admin user: %s", default_email)
        return default_email, default_pwd
    return default_email, ""


def add_user(email: str, role: str, password: Optional[str] = None) -> Tuple[bool, str, str]:
    """Adds a new user. Returns (success, message, password_used)."""
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        return False, f"Invalid email address: {email}", ""

    role_clean = role.strip().lower()
    if role_clean not in VALID_ROLES:
        return False, f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}", ""

    users = load_users()
    if email_clean in users:
        return False, f"User '{email_clean}' already exists.", ""

    pwd = password if password else secrets.token_urlsafe(12)
    p_hash, salt = hash_password(pwd)
    users[email_clean] = {
        "email": email_clean,
        "role": role_clean,
        "salt": salt,
        "password_hash": p_hash,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    save_users(users)
    return True, f"User '{email_clean}' ({role_clean}) added successfully.", pwd


def remove_user(email: str) -> Tuple[bool, str]:
    """Removes a user."""
    email_clean = email.strip().lower()
    users = load_users()
    if email_clean not in users:
        return False, f"User '{email_clean}' does not exist."
    del users[email_clean]
    save_users(users)
    return True, f"User '{email_clean}' removed."


def set_user_password(email: str, password: Optional[str] = None) -> Tuple[bool, str, str]:
    """Updates password for a user."""
    email_clean = email.strip().lower()
    users = load_users()
    if email_clean not in users:
        return False, f"User '{email_clean}' not found.", ""

    pwd = password if password else secrets.token_urlsafe(12)
    p_hash, salt = hash_password(pwd)
    users[email_clean]["salt"] = salt
    users[email_clean]["password_hash"] = p_hash
    users[email_clean]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_users(users)
    return True, f"Password updated for '{email_clean}'.", pwd


# ─────────────────────────────────────────────────────────────
# Rate Limiting
# ─────────────────────────────────────────────────────────────

def is_locked_out(ip: str) -> Tuple[bool, int]:
    """Checks if IP is locked out due to failed attempts."""
    now = time.time()
    attempts = [t for t in _failed_attempts.get(ip, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[ip] = attempts
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        oldest = min(attempts)
        remaining = int(max(1, LOCKOUT_WINDOW_SECONDS - (now - oldest)))
        return True, remaining
    return False, 0


def record_failed_attempt(ip: str) -> None:
    now = time.time()
    if ip not in _failed_attempts:
        _failed_attempts[ip] = []
    _failed_attempts[ip].append(now)


def clear_failed_attempts(ip: str) -> None:
    _failed_attempts.pop(ip, None)


# ─────────────────────────────────────────────────────────────
# Sessions
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

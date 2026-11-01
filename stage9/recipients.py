"""
stage9/recipients.py — Briefing Recipients Manager for SAGE Controller.
Stores up to 3 contacts (email, name, role, active) in stage9/state/recipients.json.
Validates RFC-5322 compliance, domain structure, and prohibits injection/separators.
Rejects test/dummy domains (@example.com, @test.com, @placeholder.com, .local).
"""

import json
import re
import email.utils
from pathlib import Path
from typing import List, Dict, Any, Tuple

RECIPIENTS_FILE = Path(__file__).resolve().parent / "state" / "recipients.json"
SENT_LOG_FILE = Path(__file__).resolve().parent / "state" / "sent_log.jsonl"

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+$"
)

REJECTED_DOMAINS = {
    "example.com", "test.com", "placeholder.com", "sample.com", "domain.com", "localhost"
}

_NAME_ROLE_REGEX = re.compile(r"^[a-zA-Z\s.\-']*$")


def validate_name_and_role(name: str = "", role: str = "") -> Tuple[bool, str]:
    """Validates name (max 60 chars) and role (max 40 chars) allowing letters, spaces, ., -, '."""
    name_clean = str(name or "").strip()
    role_clean = str(role or "").strip()
    if name_clean:
        if len(name_clean) > 60:
            return False, "Name cannot exceed 60 characters."
        if not _NAME_ROLE_REGEX.match(name_clean):
            return False, "Name can only contain letters, spaces, dots, dashes, and apostrophes."
    if role_clean:
        if len(role_clean) > 40:
            return False, "Role cannot exceed 40 characters."
        if not _NAME_ROLE_REGEX.match(role_clean):
            return False, "Role can only contain letters, spaces, dots, dashes, and apostrophes."
    return True, ""


def validate_recipient_email(addr_str: str) -> Tuple[bool, str, str]:
    """
    Validates a recipient email address strictly:
    - Parses RFC-5322 via email.utils.parseaddr.
    - Matches standard email regex with valid domain.
    - Rejects commas, semicolons, whitespace, carriage returns, newlines.
    - Rejects dummy domains (@example.com, @test.com, @placeholder.com, .local).
    Returns (is_valid, cleaned_email, error_message).
    """
    if not addr_str or not isinstance(addr_str, str):
        return False, "", "Recipient email address cannot be empty."

    # Check for forbidden control or injection characters
    if any(c in addr_str for c in ['\r', '\n', '\t', ' ', ',', ';']):
        return False, "", "Recipient email cannot contain whitespace, newlines, commas, or semicolons."

    addr_clean = addr_str.strip().lower()

    parsed_name, parsed_addr = email.utils.parseaddr(addr_clean)
    if parsed_addr != addr_clean:
        return False, "", f"Invalid email format: '{addr_str}' does not match parseaddr target."

    if not _EMAIL_REGEX.match(addr_clean):
        return False, "", f"Invalid email address '{addr_str}': must have valid user@domain.tld format."

    domain = addr_clean.split("@")[-1]
    if "." not in domain or domain.endswith(".local") or domain == "local":
        return False, "", "Invalid email domain: local/dummy domains are refused."

    if domain in REJECTED_DOMAINS:
        return False, "", f"Invalid email domain: '@{domain}' is a test/placeholder domain and is rejected."

    return True, addr_clean, ""


def get_default_recipients() -> List[Dict[str, Any]]:
    return [
        {
            "email": "sreeshanmukhtrk@gmail.com",
            "name": "Sree Shanmukh",
            "role": "Supervisor",
            "active": True
        },
        {
            "email": "trksreeshanmukh026@gmail.com",
            "name": "TRK Sree Shanmukh",
            "role": "Manager",
            "active": True
        }
    ]


def load_saved_recipients() -> List[Dict[str, Any]]:
    """Loads saved contacts from stage9/state/recipients.json. Seeds default if missing."""
    if not RECIPIENTS_FILE.exists():
        defaults = get_default_recipients()
        save_recipients(defaults, user="system_seed")
        return defaults
    try:
        data = json.loads(RECIPIENTS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            cleaned = []
            for item in data:
                if isinstance(item, dict) and "email" in item:
                    ok, clean_em, _ = validate_recipient_email(item.get("email", ""))
                    if ok:
                        cleaned.append({
                            "email": clean_em,
                            "name": str(item.get("name", "")).strip()[:80],
                            "role": str(item.get("role", "")).strip()[:80],
                            "active": bool(item.get("active", True))
                        })
            if cleaned:
                return cleaned
    except Exception:
        pass
    defaults = get_default_recipients()
    save_recipients(defaults, user="system_seed_fallback")
    return defaults


def save_recipients(contacts: List[Dict[str, Any]], user: str = "operator") -> Tuple[bool, str]:
    """
    Validates and saves up to 3 contacts.
    Returns (success, message).
    """
    if not isinstance(contacts, list):
        return False, "Contacts must be a list."

    if len(contacts) > 50:
        return False, "Maximum 50 briefing recipients allowed."

    cleaned_contacts = []
    seen_emails = set()

    for idx, c in enumerate(contacts, 1):
        if not isinstance(c, dict):
            return False, f"Contact row {idx} is invalid."
        em_raw = str(c.get("email", "")).strip()
        if not em_raw:
            continue
        ok, clean_em, err = validate_recipient_email(em_raw)
        if not ok:
            return False, f"Contact row {idx} error: {err}"
        if clean_em in seen_emails:
            return False, f"Duplicate recipient email '{clean_em}'."
        seen_emails.add(clean_em)

        name = str(c.get("name", "")).strip()
        role = str(c.get("role", "")).strip()
        ok_nr, err_nr = validate_name_and_role(name, role)
        if not ok_nr:
            return False, f"Contact row {idx} error: {err_nr}"
        active = bool(c.get("active", True))
        cleaned_contacts.append({
            "email": clean_em,
            "name": name[:60],
            "role": role[:40],
            "active": active
        })

    RECIPIENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECIPIENTS_FILE.write_text(json.dumps(cleaned_contacts, indent=2), encoding="utf-8")
    return True, f"Saved {len(cleaned_contacts)} briefing recipients."


def add_recipient(email: str, name: str = "", role: str = "", active: bool = True, user: str = "operator") -> Tuple[bool, str]:
    """Adds or updates a single contact in recipients.json."""
    existing = load_saved_recipients()
    ok_em, clean_em, err_em = validate_recipient_email(email)
    if not ok_em:
        return False, err_em
    ok_nr, err_nr = validate_name_and_role(name, role)
    if not ok_nr:
        return False, err_nr
    for c in existing:
        if c.get("email") == clean_em:
            c["name"] = name[:60]
            c["role"] = role[:40]
            c["active"] = active
            return save_recipients(existing, user=user)
    existing.append({
        "email": clean_em,
        "name": name[:60],
        "role": role[:40],
        "active": active
    })
    return save_recipients(existing, user=user)


def delete_recipient(email: str, user: str = "operator") -> Tuple[bool, str]:
    """Deletes a contact by email from recipients.json."""
    existing = load_saved_recipients()
    clean_em = email.strip().lower()
    updated = [c for c in existing if c.get("email") != clean_em]
    if len(updated) == len(existing):
        return False, f"Contact '{email}' not found."
    return save_recipients(updated, user=user)



def load_send_history(limit: int = 5) -> List[Dict[str, Any]]:
    """Loads the last N send records from stage9/state/sent_log.jsonl."""
    if not SENT_LOG_FILE.exists():
        return []
    records = []
    try:
        with open(SENT_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []

    # Newest first
    records.reverse()
    formatted = []
    for r in records[:limit]:
        status_raw = r.get("status", "")
        if "LIVE" in status_raw or status_raw == "SUCCESS":
            disp_status = "Sent"
            badge = "pill pill-green"
        elif "DRY_RUN" in status_raw:
            disp_status = "Dry run"
            badge = "pill pill-amber"
        else:
            disp_status = "Failed"
            badge = "pill pill-red"

        ts = r.get("timestamp", "")
        # Format timestamp to readable string
        ts_disp = ts.replace("T", " ")[:19] if ts else "—"

        formatted.append({
            "recipient": r.get("recipient", "—"),
            "timestamp": ts_disp,
            "status": disp_status,
            "badge": badge,
            "digest_date": r.get("as_of", "—"),
            "mode": r.get("mode", "manual")
        })
    return formatted

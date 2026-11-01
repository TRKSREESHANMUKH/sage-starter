"""
stage9/send_check.py — Non-interactive email delivery validation tool.

Usage:
    ./venv/bin/python -m stage9.send_check [--live] [--as-of YYYY-MM-DD] [--recipient EMAIL]

Safely validates SMTP credentials and prepares/dispatches daily reports.
Never prints or logs passwords/secrets.
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import date, datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure .env is loaded
env_file = ROOT_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from stage9.ops import ensure_report, send_report_now_v6, get_allowlist


def test_smtp_connection():
    import smtplib
    if os.getenv("SAGE_MAIL_TRANSPORT", "").lower() == "mock":
        return True, "Mock SMTP connection successful (test mode)."

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except Exception:
        port = 587
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()

    if not user:
        return False, "SMTP configuration error: SMTP_USER is unset in .env"
    if not password or password == "dev_dummy_password":
        return False, "SMTP configuration error: SMTP_PASSWORD is unset or placeholder in .env"

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
            server.ehlo()
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()
    except (smtplib.SMTPConnectError, ConnectionRefusedError, OSError) as exc:
        return False, f"Network error connecting to {host}:{port}: {exc}"
    except Exception as exc:
        return False, f"TLS / Handshake error with {host}:{port}: {exc}"

    try:
        server.login(user, password)
    except smtplib.SMTPAuthenticationError as exc:
        err_msg = exc.smtp_error.decode() if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
        return False, f"SMTP authentication failed: check the app password in .env ({err_msg})"
    except Exception as exc:
        return False, f"SMTP login failed: {exc}"
    finally:
        try:
            server.quit()
        except Exception:
            pass

    return True, f"OK: Connected and authenticated to {host}:{port} as {user}"


def main():
    parser = argparse.ArgumentParser(description="SAGE Email Delivery Verification Tool")
    parser.add_argument("--smtp-test", action="store_true", help="Connect, start TLS and authenticate without sending message")
    parser.add_argument("--live", action="store_true", help="Execute live SMTP delivery via Gmail")
    parser.add_argument("--as-of", type=str, default="2025-12-31", help="Report as-of date (YYYY-MM-DD)")
    parser.add_argument("--recipient", type=str, default=None, help="Recipient email address")
    args = parser.parse_args()

    if args.smtp_test:
        ok, msg = test_smtp_connection()
        if ok:
            print(msg)
            sys.exit(0)
        else:
            print(f"FAILED: {msg}", file=sys.stderr)
            sys.exit(1)

    as_of = date.fromisoformat(args.as_of)
    recipient = args.recipient or os.getenv("SAGE_DEMO_RECIPIENT", "sreeshanmukhtrk@gmail.com").strip()

    print("=" * 70)
    print("SAGE LIVE SEND VERIFICATION & HEALTH CHECK")
    print("=" * 70)
    print(f"Target Date : {as_of.isoformat()}")
    print(f"Recipient   : {recipient}")
    print(f"Mode        : {'LIVE (Real Gmail SMTP)' if args.live else 'DRY-RUN (Simulated Delivery)'}")

    # 1. Verify recipient allowlist
    allowlist = get_allowlist()
    if recipient.strip().lower() not in allowlist:
        print(f"FAILED: Recipient '{recipient}' is not permitted by allowlist.")
        sys.exit(1)
    print(f"Allowlist   : PASSED ({recipient} is verified)")

    # 2. Check credentials safely (never log password value)
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    send_enabled = os.getenv("SAGE_SEND_ENABLED", "false").lower() in ("true", "1", "yes")

    is_placeholder = (
        not smtp_pass
        or smtp_pass.startswith("your_")
        or "placeholder" in smtp_pass.lower()
        or len(smtp_pass.replace(" ", "")) < 12
    )

    print(f"SMTP Host   : {smtp_host}:{smtp_port}")
    print(f"SMTP User   : {smtp_user if smtp_user else '[NOT SET]'}")
    print(f"Credentials : {'CONFIGURED (Password is set & non-placeholder)' if not is_placeholder else 'PLACEHOLDER / MISSING'}")
    print(f"Send Enabled: {send_enabled}")

    if args.live:
        if not send_enabled:
            print(f"\nFAILED: Live delivery requires SAGE_SEND_ENABLED=true in .env (currently: {os.getenv('SAGE_SEND_ENABLED', 'false')}).")
            sys.exit(1)
        if is_placeholder:
            print("\nFAILED: Live delivery requires non-placeholder SMTP credentials in .env.")
            sys.exit(1)

    # 3. Ensure report is built
    print("\nEnsuring report artifacts exist...")
    paths = ensure_report(as_of=as_of, user="send_check")
    print(f"HTML Report : {paths.html}")
    print(f"PDF Report  : {paths.pdf} (Exists: {paths.pdf.exists()})")

    # 4. Dispatch
    print("\nDispatching report...")
    res = send_report_now_v6(
        recipient=recipient,
        as_of=as_of,
        force_live=args.live,
        force_dry_run=(not args.live),
        user="send_check"
    )

    status = res.get("status")
    smtp_code = res.get("smtp_code", "—")
    msg_id = res.get("message_id", "—")
    sent_at = res.get("sent_at", datetime.now().isoformat())
    conn_time = res.get("connection_time_ms", 0)

    print("\n--- DISPATCH RESULT ---")
    print(f"Status      : {status}")
    print(f"SMTP Code   : {smtp_code}")
    print(f"Message-ID  : {msg_id}")
    print(f"Sent At     : {sent_at}")
    print(f"Duration    : {conn_time:.2f} ms")

    if args.live:
        if status == "SUCCESS_LIVE":
            print("\n✓ LIVE DELIVERY SUCCESSFUL! Check inbox (and Spam folder) of recipient.")
            sys.exit(0)
        else:
            print(f"\n✗ LIVE DELIVERY FAILED: {res.get('error', 'Unknown SMTP error')}")
            sys.exit(1)
    else:
        if status != "SUCCESS_DRY_RUN":
            print(f"\n✗ DRY-RUN FAILED: Expected SUCCESS_DRY_RUN but got status {status}")
            sys.exit(1)
        print("\n✓ DRY-RUN SUCCESSFUL! (No live email was dispatched to Gmail).")
        print("To deliver a real email to the owner, run:")
        print(f"    ./venv/bin/python -m stage9.send_check --live --as-of {as_of.isoformat()}")
        sys.exit(0)


if __name__ == "__main__":
    main()

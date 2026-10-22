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


def main():
    parser = argparse.ArgumentParser(description="SAGE Email Delivery Verification Tool")
    parser.add_argument("--live", action="store_true", help="Execute live SMTP delivery via Gmail")
    parser.add_argument("--as-of", type=str, default="2025-12-31", help="Report as-of date (YYYY-MM-DD)")
    parser.add_argument("--recipient", type=str, default=None, help="Recipient email address")
    args = parser.parse_args()

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
        print("\n✓ DRY-RUN SUCCESSFUL! (No live email was dispatched to Gmail).")
        print("To deliver a real email to the owner, run:")
        print(f"    ./venv/bin/python -m stage9.send_check --live --as-of {as_of.isoformat()}")


if __name__ == "__main__":
    main()

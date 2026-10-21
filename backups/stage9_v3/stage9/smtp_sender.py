"""
stage9/smtp_sender.py
──────────────────────
MIME email assembly and SMTP delivery layer for SAGE causal attribution reports.

Features:
  • Two-part MIME (text/plain and text/html) alternative payload.
  • Dry-run mode for local development and CI testing (records to file).
  • Configurable SMTP with STARTTLS and authentication.
  • Logs delivery telemetry and timestamps.
"""

from __future__ import annotations

import email.utils
import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SAGE_SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SAGE_SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SAGE_SMTP_USER", "")
SMTP_PASS = os.getenv("SAGE_SMTP_PASS", "")
SMTP_FROM = os.getenv("SAGE_SMTP_FROM", "sage-causal@internal.corp")
SMTP_TO   = [addr.strip() for addr in os.getenv("SAGE_SMTP_TO", "supply-chain-ops@internal.corp").split(",")]
SMTP_USE_TLS = os.getenv("SAGE_SMTP_TLS", "false").lower() in ("1", "true", "yes")

# When True or when SMTP is unreachable, messages are saved locally without throwing network errors
SMTP_DRY_RUN = os.getenv("SAGE_SMTP_DRY_RUN", "true").lower() in ("1", "true", "yes")

DELIVERY_LOG_PATH = Path(__file__).resolve().parent.parent / "analytics" / "report_delivery_log.json"


def create_mime_message(
    subject: str,
    text_content: str,
    html_content: str,
    from_addr: str = SMTP_FROM,
    to_addrs: list[str] | None = None,
) -> MIMEMultipart:
    """Creates a multipart/alternative MIME message with both plain-text and HTML versions."""
    to_list = to_addrs or SMTP_TO

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(to_list)
    msg["Date"]    = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain="sage.internal")

    part_text = MIMEText(text_content, "plain", "utf-8")
    part_html = MIMEText(html_content, "html", "utf-8")

    # Plain text first, HTML second (RFC preference)
    msg.attach(part_text)
    msg.attach(part_html)

    return msg


def send_report(
    subject: str,
    text_content: str,
    html_content: str,
    to_addrs: list[str] | None = None,
    dry_run: bool = SMTP_DRY_RUN,
) -> dict[str, Any]:
    """
    Delivers or dry-runs delivery of the SAGE attribution report.

    Returns:
        Receipt dict containing status, timestamp, recipients, and message ID.
    """
    to_list = to_addrs or SMTP_TO
    msg = create_mime_message(subject, text_content, html_content, to_addrs=to_list)
    msg_id = msg["Message-ID"]
    now_iso = datetime.now(timezone.utc).isoformat()

    receipt: dict[str, Any] = {
        "message_id":  msg_id,
        "timestamp":   now_iso,
        "subject":     subject,
        "recipients":  to_list,
        "from":        msg["From"],
        "dry_run":     dry_run,
        "status":      "PENDING",
    }

    if dry_run:
        logger.info("[DRY-RUN] SAGE Report '%s' recorded for recipients: %s", subject, to_list)
        receipt["status"] = "DRY_RUN_SAVED"
        _append_delivery_log(receipt)
        return receipt

    try:
        logger.info("Connecting to SMTP server at %s:%d ...", SMTP_HOST, SMTP_PORT)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(msg["From"], to_list, msg.as_string())

        logger.info("Report successfully dispatched via SMTP to %s", to_list)
        receipt["status"] = "SENT"

    except (ConnectionRefusedError, smtplib.SMTPException, OSError) as exc:
        logger.warning("SMTP delivery failed (%s); recording as FAILED_FALLBACK_SAVED", exc)
        receipt["status"] = "FAILED"
        receipt["error"]  = str(exc)

    _append_delivery_log(receipt)
    return receipt


def _append_delivery_log(receipt: dict[str, Any]) -> None:
    DELIVERY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logs = []
    if DELIVERY_LOG_PATH.exists():
        try:
            with DELIVERY_LOG_PATH.open() as fh:
                logs = json.load(fh)
        except Exception:
            logs = []

    logs.append(receipt)
    with DELIVERY_LOG_PATH.open("w") as fh:
        json.dump(logs, fh, indent=2)

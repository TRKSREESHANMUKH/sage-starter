"""
stage9/scheduler.py — SAGE Phase E: Delivery Engine & 8:00 PM Daily Email Runner.

Responsibilities:
- Reads schedule configuration from stage9/config/schedule.yaml.
- Schedules exactly one job: nightly_digest at 20:00 daily (Asia/Kolkata timezone).
- Merges causal findings and operational digest into one single email.
- Attaches the one-page PDF of the digest to the email (MIME application/pdf).
- Idempotency Guarantee:
    - Appends delivery records to stage9/state/sent_log.jsonl keyed by (job, as_of).
    - Never delivers twice for the same date or calendar day.
- Catch-up Logic & CLI Flags:
    --run-due    : Runs due digest for current replay date if not already sent today,
                   advances replay pointer by 1 day, and exits.
    --test-send  : Sends single test mail to SMTP_USER with PDF attached.
    --as-of DATE : Override simulation date.
    --force      : Bypass idempotency check.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import logging
import os
from pathlib import Path
import smtplib
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.clock import get_as_of_date, advance_replay_date
from stage9.render_email import render_causal_findings_brief, render_nightly_digest, assert_one_page_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("stage9.scheduler")

SCHEDULE_CONFIG_PATH = ROOT_DIR / "stage9" / "config" / "schedule.yaml"
SENT_LOG_PATH = ROOT_DIR / "stage9" / "state" / "sent_log.jsonl"
DELIVERY_LOG_PATH = ROOT_DIR / "analytics" / "report_delivery_log.json"


def load_schedule_config() -> Dict[str, Any]:
    if SCHEDULE_CONFIG_PATH.exists():
        with open(SCHEDULE_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "timezone": "Asia/Kolkata",
        "jobs": {
            "nightly_digest": {"cron": "0 20 * * *"}
        },
        "recipients": {
            "nightly_digest": ["plant-manager@sage-plant.local"]
        }
    }


def get_sent_keys() -> Set[str]:
    keys: Set[str] = set()
    if SENT_LOG_PATH.exists():
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    k = f"{entry.get('job')}:{entry.get('as_of')}"
                    keys.add(k)
                    if "extra_key" in entry:
                        keys.add(entry["extra_key"])
                except Exception:
                    continue
    return keys


def record_sent_log(
    job: str,
    as_of: date,
    recipients: List[str],
    status: str,
    mode: str,
    extra_key: Optional[str] = None
) -> None:
    SENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job": job,
        "as_of": as_of.isoformat(),
        "recipients": recipients,
        "status": status,
        "delivery_mode": mode
    }
    if extra_key:
        entry["extra_key"] = extra_key

    with open(SENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    DELIVERY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    delivery_history: List[Dict[str, Any]] = []
    if DELIVERY_LOG_PATH.exists():
        try:
            with open(DELIVERY_LOG_PATH, "r", encoding="utf-8") as f:
                delivery_history = json.load(f)
        except Exception:
            delivery_history = []
    delivery_history.append(entry)
    with open(DELIVERY_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(delivery_history, f, indent=2)


def dispatch_email(
    subject: str,
    html_body: str,
    text_body: str,
    recipients: List[str],
    job_name: str,
    as_of: date,
    attach_pdf: bool = True
) -> bool:
    """
    Dispatches email via SMTP if enabled, otherwise records dry-run telemetry.
    Attaches the 1-page PDF if attach_pdf is True.
    """
    is_live = os.getenv("SAGE_SEND_ENABLED", "false").lower() in ("true", "1", "yes")

    # Generate PDF attachment
    pdf_bytes: Optional[bytes] = None
    if attach_pdf:
        _, _, pdf_bytes = assert_one_page_pdf(html_body)

    if not is_live:
        logger.info("[DRY-RUN] Delivery simulation for %s (as_of: %s)", job_name, as_of.isoformat())
        logger.info("[DRY-RUN] Subject: %s", subject)
        logger.info("[DRY-RUN] Recipients: %s", recipients)
        if pdf_bytes:
            logger.info("[DRY-RUN] PDF Attachment generated: %d bytes (1 page confirmed)", len(pdf_bytes))
        record_sent_log(job_name, as_of, recipients, status="SUCCESS_DRY_RUN", mode="dry_run")
        return True

    # Live SMTP Dispatch with 3 retries
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", user or "sage-alerts@example.com")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)

    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt_part)

    if pdf_bytes:
        pdf_attach = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_filename = f"sage_operations_brief_{as_of.isoformat()}.pdf"
        pdf_attach.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(pdf_attach)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Attempting live SMTP delivery for %s to %s (attempt %d/%d)...", job_name, recipients, attempt, max_retries)
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.starttls()

            if user and password:
                server.login(user, password)

            server.sendmail(from_addr, recipients, msg.as_string())
            server.quit()
            logger.info("SMTP delivery successful for %s: SUCCESS", job_name)
            record_sent_log(job_name, as_of, recipients, status="SUCCESS", mode="live_smtp")
            return True

        except Exception as exc:
            logger.error("SMTP delivery failed (attempt %d): %s", attempt, exc)
            if attempt < max_retries:
                backoff = 2 ** attempt
                logger.info("Backing off for %d seconds...", backoff)
                time.sleep(backoff)
            else:
                record_sent_log(job_name, as_of, recipients, status=f"FAILED: {exc}", mode="live_smtp")
                return False

    return False


def execute_job(
    job_name: str,
    as_of: Optional[date] = None,
    force: bool = False,
    advance_pointer: bool = True
) -> bool:
    """
    Executes a scheduled job with idempotency protection.
    """
    cfg = load_schedule_config()
    current_as_of = as_of or get_as_of_date()
    sent_keys = get_sent_keys()
    key = f"{job_name}:{current_as_of.isoformat()}"

    if key in sent_keys and not force:
        logger.warning("Idempotency: Job '%s' for date '%s' already executed; skipping duplicate.", job_name, current_as_of.isoformat())
        return True

    recipients = cfg.get("recipients", {}).get(job_name, ["plant-manager@sage-plant.local"])

    if job_name == "nightly_digest":
        subject, html, text = render_nightly_digest(current_as_of)
    elif job_name == "findings_brief":
        subject, html, text = render_causal_findings_brief(current_as_of)
    else:
        raise ValueError(f"Unknown job: {job_name}")

    success = dispatch_email(subject, html, text, recipients, job_name, current_as_of, attach_pdf=True)

    if success and job_name == "nightly_digest" and advance_pointer:
        advance_replay_date(current_as_of)

    return success


def run_due(force: bool = False) -> bool:
    """
    Catch-up and OS runner logic:
    Checks if nightly_digest has already been sent for the current real calendar day
    or current replay date. If not sent yet, sends it, advances replay clock by 1 day, and exits.
    If already sent, outputs 'already sent' and skips.
    """
    real_today = date.today()
    current_replay = get_as_of_date()
    sent_keys = get_sent_keys()

    key_replay = f"nightly_digest:{current_replay.isoformat()}"
    key_real = f"nightly_digest:real_{real_today.isoformat()}"

    if (key_replay in sent_keys or key_real in sent_keys) and not force:
        print(f"[INFO] Nightly digest already sent for calendar day {real_today.isoformat()} / replay date {current_replay.isoformat()}.")
        print("already sent")
        return True

    print(f"[INFO] Running due nightly digest for replay date {current_replay.isoformat()} (Calendar day: {real_today.isoformat()})...")
    cfg = load_schedule_config()
    recipients = cfg.get("recipients", {}).get("nightly_digest", ["plant-manager@sage-plant.local"])
    subject, html, text = render_nightly_digest(current_replay)

    success = dispatch_email(subject, html, text, recipients, "nightly_digest", current_replay, attach_pdf=True)
    if success:
        record_sent_log(
            job="nightly_digest",
            as_of=current_replay,
            recipients=recipients,
            status="SUCCESS",
            mode="run_due",
            extra_key=key_real
        )
        next_d = advance_replay_date(current_replay)
        print(f"[INFO] SUCCESS: Nightly digest for {current_replay.isoformat()} sent. Advanced replay date to {next_d.isoformat()}.")
        return True
    return False


def test_send(as_of: Optional[date] = None) -> bool:
    """Sends a single test email only to SMTP_USER with PDF attached."""
    user = os.getenv("SMTP_USER", "")
    if not user:
        user = "operations-owner@example.com"
    current_as_of = as_of or get_as_of_date()
    logger.info("Executing test send to owner address: %s for as_of: %s", user, current_as_of.isoformat())

    subject, html, text = render_nightly_digest(current_as_of)
    subject = f"[TEST SEND] {subject}"
    return dispatch_email(subject, html, text, [user], "test_send", current_as_of, attach_pdf=True)


def start_scheduler() -> None:
    """Runs the blocking APScheduler service for exactly one 20:00 daily job."""
    cfg = load_schedule_config()
    tz_name = cfg.get("timezone", "Asia/Kolkata")
    tz = pytz.timezone(tz_name)

    scheduler = BlockingScheduler(timezone=tz)
    jobs_cfg = cfg.get("jobs", {})

    nd_cron = jobs_cfg.get("nightly_digest", {}).get("cron", "0 20 * * *")
    nd_parts = nd_cron.split()
    scheduler.add_job(
        func=lambda: execute_job("nightly_digest"),
        trigger=CronTrigger(
            minute=nd_parts[0],
            hour=nd_parts[1],
            day=nd_parts[2],
            month=nd_parts[3],
            day_of_week=nd_parts[4],
            timezone=tz
        ),
        id="nightly_digest",
        name="SAGE 8:00 PM Nightly Operations Digest",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600
    )

    logger.info("Starting SAGE Stage 9 Delivery Scheduler (Timezone: %s)...", tz_name)
    logger.info("Nightly Digest scheduled: %s (20:00 Asia/Kolkata)", nd_cron)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped cleanly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAGE Stage 9 Scheduler CLI")
    parser.add_argument("--now", choices=["nightly_digest", "findings_brief"], help="Execute job immediately")
    parser.add_argument("--run-due", action="store_true", help="Run due nightly digest for current replay date with catch-up")
    parser.add_argument("--as-of", type=str, help="Override as-of date (YYYY-MM-DD)")
    parser.add_argument("--test-send", action="store_true", help="Send test email to owner SMTP_USER")
    parser.add_argument("--force", action="store_true", help="Bypass idempotency check")
    args = parser.parse_args()

    as_of_override = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else None

    if args.test_send:
        ok = test_send(as_of=as_of_override)
        sys.exit(0 if ok else 1)
    elif args.run_due:
        ok = run_due(force=args.force)
        sys.exit(0 if ok else 1)
    elif args.now:
        ok = execute_job(args.now, as_of=as_of_override, force=args.force)
        sys.exit(0 if ok else 1)
    else:
        start_scheduler()

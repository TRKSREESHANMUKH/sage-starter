"""
stage9/scheduler.py — SAGE Phase E: Delivery Engine & APScheduler Runner.

Responsibilities:
- Reads schedule configuration from stage9/config/schedule.yaml.
- Schedules two jobs with APScheduler CronTrigger (Asia/Kolkata timezone):
    1. findings_brief (default 08:00 daily)
    2. nightly_digest (default 21:00 daily)
- Idempotency Guarantee:
    - Appends delivery records to stage9/state/sent_log.jsonl keyed by (job, as_of).
    - Never delivers twice for the same (job, as_of) key.
- Dry-Run by Default:
    - Only sends live SMTP email if SAGE_SEND_ENABLED="true" in .env.
    - Otherwise logs full telemetry to analytics/report_delivery_log.json and sent_log.jsonl.
- CLI Flags:
    --now findings_brief|nightly_digest  : Run job immediately for current as_of
    --as-of YYYY-MM-DD                   : Override simulation date
    --test-send                          : Send test email to SMTP_USER
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
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
from stage9.render_email import render_causal_findings_brief, render_nightly_digest

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
            "findings_brief": {"cron": "0 8 * * *"},
            "nightly_digest": {"cron": "0 21 * * *"}
        },
        "recipients": {
            "findings_brief": ["operations-leadership@sage-plant.local"],
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
                except Exception:
                    continue
    return keys


def record_sent_log(job: str, as_of: date, recipients: List[str], status: str, mode: str) -> None:
    SENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job": job,
        "as_of": as_of.isoformat(),
        "recipients": recipients,
        "status": status,
        "delivery_mode": mode
    }
    with open(SENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Also append to legacy delivery log in analytics/
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
    as_of: date
) -> bool:
    """
    Dispatches email via SMTP if enabled, otherwise records dry-run telemetry.
    Supports 3 retries with exponential backoff.
    """
    is_live = os.getenv("SAGE_SEND_ENABLED", "false").lower() in ("true", "1", "yes")

    if not is_live:
        logger.info("[DRY-RUN] Delivery simulation for %s (as_of: %s)", job_name, as_of.isoformat())
        logger.info("[DRY-RUN] Subject: %s", subject)
        logger.info("[DRY-RUN] Recipients: %s", recipients)
        record_sent_log(job_name, as_of, recipients, status="SUCCESS_DRY_RUN", mode="dry_run")
        return True

    # Live SMTP Dispatch with 3 retries
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", user or "sage-alerts@example.com")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Attempting SMTP delivery for %s (attempt %d/%d)...", job_name, attempt, max_retries)
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.starttls()

            if user and password:
                server.login(user, password)

            server.sendmail(from_addr, recipients, msg.as_string())
            server.quit()
            logger.info("SMTP delivery successful for %s", job_name)
            record_sent_log(job_name, as_of, recipients, status="SUCCESS_LIVE_SMTP", mode="live_smtp")
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


def execute_job(job_name: str, as_of: Optional[date] = None, force: bool = False) -> bool:
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

    if job_name == "findings_brief":
        subject, html, text = render_causal_findings_brief(current_as_of)
    elif job_name == "nightly_digest":
        subject, html, text = render_nightly_digest(current_as_of)
    else:
        raise ValueError(f"Unknown job: {job_name}")

    success = dispatch_email(subject, html, text, recipients, job_name, current_as_of)

    # In replay mode, advance clock after successful nightly digest
    if success and job_name == "nightly_digest" and as_of is None:
        advance_replay_date(current_as_of)

    return success


def test_send(as_of: Optional[date] = None) -> bool:
    """Sends a single test email only to SMTP_USER or prints dry-run telemetry."""
    user = os.getenv("SMTP_USER", "operations-test@sage-plant.local")
    current_as_of = as_of or get_as_of_date()
    logger.info("Executing test send to: %s for as_of: %s", user, current_as_of.isoformat())

    subject, html, text = render_nightly_digest(current_as_of)
    subject = f"[TEST SEND] {subject}"
    return dispatch_email(subject, html, text, [user], "test_send", current_as_of)


def start_scheduler() -> None:
    """Runs the blocking APScheduler service."""
    cfg = load_schedule_config()
    tz_name = cfg.get("timezone", "Asia/Kolkata")
    tz = pytz.timezone(tz_name)

    scheduler = BlockingScheduler(timezone=tz)
    jobs_cfg = cfg.get("jobs", {})

    # Findings Brief cron
    fb_cron = jobs_cfg.get("findings_brief", {}).get("cron", "0 8 * * *")
    fb_parts = fb_cron.split()
    scheduler.add_job(
        func=lambda: execute_job("findings_brief"),
        trigger=CronTrigger(
            minute=fb_parts[0],
            hour=fb_parts[1],
            day=fb_parts[2],
            month=fb_parts[3],
            day_of_week=fb_parts[4],
            timezone=tz
        ),
        id="findings_brief",
        name="SAGE Findings Brief",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600
    )

    # Nightly Digest cron
    nd_cron = jobs_cfg.get("nightly_digest", {}).get("cron", "0 21 * * *")
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
        name="SAGE Nightly Digest",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600
    )

    logger.info("Starting SAGE Stage 9 Delivery Scheduler (Timezone: %s)...", tz_name)
    logger.info("Findings Brief scheduled: %s", fb_cron)
    logger.info("Nightly Digest scheduled: %s", nd_cron)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped cleanly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAGE Stage 9 Scheduler CLI")
    parser.add_argument("--now", choices=["findings_brief", "nightly_digest"], help="Execute job immediately")
    parser.add_argument("--as-of", type=str, help="Override as-of date (YYYY-MM-DD)")
    parser.add_argument("--test-send", action="store_true", help="Send test email only to SMTP_USER")
    parser.add_argument("--force", action="store_true", help="Bypass idempotency check")
    args = parser.parse_args()

    as_of_override = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else None

    if args.test_send:
        ok = test_send(as_of=as_of_override)
        sys.exit(0 if ok else 1)
    elif args.now:
        ok = execute_job(args.now, as_of=as_of_override, force=args.force)
        sys.exit(0 if ok else 1)
    else:
        start_scheduler()

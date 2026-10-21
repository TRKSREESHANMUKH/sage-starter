"""
stage9/scheduler.py
────────────────────
Automated reporting daemon using APScheduler.

Features:
  • Runs scheduled weekly/periodic reports.
  • Provides on-demand trigger function `trigger_report_now()`.
  • Seamlessly connects Stage 8 narration outputs to Stage 9 SMTP delivery.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from stage8.common import ANALYTICS_DIR
from stage9.report_builder import build_html_report, build_subject, build_text_report
from stage9.smtp_sender import send_report

logger = logging.getLogger(__name__)

NARRATION_RESULTS_PATH = ANALYTICS_DIR / "narration_results.json"


def generate_and_dispatch_report(dry_run: bool = True) -> dict[str, Any]:
    """
    Core job task:
      1. Reads narration_results.json.
      2. Formats email subject, text, and HTML parts.
      3. Dispatches via SMTP (or dry-run log).
    """
    if not NARRATION_RESULTS_PATH.exists():
        raise FileNotFoundError(
            f"Narration results not found at {NARRATION_RESULTS_PATH}. "
            "Execute Stage 8 before generating Stage 9 reports."
        )

    with NARRATION_RESULTS_PATH.open() as fh:
        narration_data = json.load(fh)

    subject = build_subject(narration_data)
    text_content = build_text_report(narration_data)
    html_content = build_html_report(narration_data)

    receipt = send_report(
        subject=subject,
        text_content=text_content,
        html_content=html_content,
        dry_run=dry_run,
    )
    logger.info("Report task finished. Status: %s (Msg ID: %s)", receipt["status"], receipt["message_id"])
    return receipt


def setup_scheduler(
    cron_day_of_week: str = "mon",
    cron_hour: int = 8,
    cron_minute: int = 0,
    blocking: bool = False,
    dry_run: bool = True,
) -> BackgroundScheduler | BlockingScheduler:
    """Configures APScheduler for weekly causal report delivery."""
    scheduler_cls = BlockingScheduler if blocking else BackgroundScheduler
    scheduler = scheduler_cls()

    trigger = CronTrigger(
        day_of_week=cron_day_of_week,
        hour=cron_hour,
        minute=cron_minute,
        timezone="UTC",
    )

    scheduler.add_job(
        generate_and_dispatch_report,
        trigger=trigger,
        kwargs={"dry_run": dry_run},
        id="sage_weekly_attribution_report",
        name="SAGE Weekly Causal Attribution Report Dispatch",
        replace_existing=True,
    )

    logger.info(
        "Scheduled SAGE report job for %s %02d:%02d UTC (blocking=%s, dry_run=%s)",
        cron_day_of_week.upper(), cron_hour, cron_minute, blocking, dry_run
    )
    return scheduler


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if "--now" in sys.argv or len(sys.argv) == 1:
        print("\nTriggering on-demand SAGE causal report dispatch ...")
        receipt = generate_and_dispatch_report(dry_run=True)
        print("Report Dispatched Successfully:")
        print(f"  Status    : {receipt['status']}")
        print(f"  Subject   : {receipt['subject']}")
        print(f"  Message ID: {receipt['message_id']}")
        print(f"  Recipients: {', '.join(receipt['recipients'])}")
        print(f"  Timestamp : {receipt['timestamp']}")
    elif "--daemon" in sys.argv:
        sched = setup_scheduler(blocking=True, dry_run=True)
        print("Starting SAGE Report Scheduler Daemon (Ctrl+C to stop) ...")
        sched.start()

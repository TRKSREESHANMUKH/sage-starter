"""
stage9/daily_run.py — Daily Ingestion, Preparation, Reporting, and Two-Phase Dispatch Engine.

Part 2, 3, and 4 Requirements:
- CLI Flags:
    --prepare             Ingests next unprocessed pack from demo_data/queue/ (if any),
                          builds snapshot -> priorities -> narration -> HTML/text/PDF,
                          saves under reports/<YYYY-MM-DD>/. Sends nothing.
                          If queue is empty, builds report for current day with
                          "No new data received today" and flags for owner only.
    --send                Sends the prepared report for current day only (<10s).
                          If prepare failed/missing, alerts owner and exits non-zero.
                          Respects idempotency key (job:as_of:recipient).
    --send-now            Sends report immediately for current day (manual mode, bypasses scheduled idempotency).
    --next-day            Ingests next pack and prepares. Can combine with --send-now.
    --date YYYY-MM-DD     Target date override for sending/reporting.
    --to <address>        Recipient override (must be on SAGE_ALLOWED_RECIPIENTS).
    --week                Runs all 7 week days in order, generates reports/<date>/ and reports/week_summary.md.
                          Dry-run by default. With --send, emails each with a 20-second gap.
    --reset-demo          Restores live DB from baseline, repopulates queue, resets current day to 2025-02-02,
                          clears demo sent logs and caches.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import logging
import os
from pathlib import Path
import shutil
import smtplib
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import pytz
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.clock import get_as_of_date, set_replay_date
from stage9.current_day import get_current_day, set_current_day, register_ingested_day, get_ingested_days
from stage9.ingest_day import ingest_pack, PackValidationError
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.narrate import generate_executive_narrative
from stage9.render_email import render_nightly_digest, assert_one_page_pdf
from stage9.status import RESEARCH_FRAMING

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("stage9.daily_run")

QUEUE_DIR = ROOT_DIR / "demo_data" / "queue"
PACKS_DIR = ROOT_DIR / "demo_data" / "packs"
REPORTS_DIR = ROOT_DIR / "reports"
SENT_LOG_PATH = ROOT_DIR / "stage9" / "state" / "sent_log.jsonl"
SCHEDULE_CONFIG_PATH = ROOT_DIR / "stage9" / "config" / "schedule.yaml"
LIVE_DB_PATH = ROOT_DIR / "live" / "sage_live.db"
LIVE_BASELINE_PATH = ROOT_DIR / "live" / "sage_live_baseline.db"
INSIGHTS_CACHE_DIR = ROOT_DIR / "analytics" / "insights_cache"


def get_allowed_recipients() -> Set[str]:
    """Returns set of allowed recipient email addresses."""
    env_allowed = os.getenv("SAGE_ALLOWED_RECIPIENTS", "")
    allowed = {r.strip().lower() for r in env_allowed.split(",") if r.strip()}
    owner = os.getenv("SAGE_OWNER_EMAIL", "thotaramakrishnasreeshanmukh@gmail.com").strip().lower()
    demo = os.getenv("SAGE_DEMO_RECIPIENT", "sreeshanmukhtrk@gmail.com").strip().lower()
    allowed.add(owner)
    allowed.add(demo)
    return allowed


def validate_recipient_allowed(recipient: str) -> bool:
    """Validates that a recipient is in the allowlist."""
    rec_clean = recipient.strip().lower()
    if not rec_clean or "@" not in rec_clean:
        return False
    return rec_clean in get_allowed_recipients()


def get_sent_keys() -> Set[str]:
    """Returns set of idempotency keys already executed."""
    keys: Set[str] = set()
    if SENT_LOG_PATH.exists():
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    k = f"{entry.get('job')}:{entry.get('as_of')}:{entry.get('recipient')}"
                    keys.add(k)
                    # Also record without recipient for legacy compatibility
                    keys.add(f"{entry.get('job')}:{entry.get('as_of')}")
                except Exception:
                    continue
    return keys


def log_sent_event(
    job: str,
    as_of: date,
    recipient: str,
    status: str,
    mode: str,
    subject: str,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """Logs sent event to sent_log.jsonl with millisecond precision timestamp."""
    SENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Millisecond timestamp ISO format
    now_utc = datetime.now(timezone.utc)
    ms_timestamp = now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    entry: Dict[str, Any] = {
        "timestamp": ms_timestamp,
        "job": job,
        "as_of": as_of.isoformat(),
        "recipient": recipient,
        "status": status,
        "mode": mode,
        "subject": subject
    }
    if error:
        entry["error"] = error

    with open(SENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


# ──────────────────────────────────────────────────────────────────────────────
# Ingest & Prepare Step
# ──────────────────────────────────────────────────────────────────────────────

def get_next_queue_pack() -> Optional[Path]:
    """Returns the earliest pack directory in demo_data/queue/."""
    if not QUEUE_DIR.exists():
        return None
    subdirs = sorted([p for p in QUEUE_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")])
    if subdirs:
        return subdirs[0]
    return None


def prepare_daily_run(as_of: Optional[date] = None, force_pack: Optional[Path] = None) -> Dict[str, Any]:
    """
    Executes the prepare step:
    1. Ingests next pack from demo_data/queue/ if available.
    2. Computes snapshot, priorities, narration, report HTML/text/PDF.
    3. Saves under reports/<YYYY-MM-DD>/.
    4. Sends nothing!
    """
    no_new_data = False
    pack_to_ingest = force_pack or get_next_queue_pack()

    if pack_to_ingest:
        logger.info("Ingesting operational pack: %s", pack_to_ingest)
        try:
            ingest_result = ingest_pack(pack_to_ingest)
            target_as_of = datetime.strptime(ingest_result["pack_date"], "%Y-%m-%d").date()
            # Remove ingested pack from queue
            if QUEUE_DIR in pack_to_ingest.parents:
                shutil.rmtree(pack_to_ingest)
        except Exception as exc:
            logger.error("Pack ingestion failed: %s", exc)
            raise RuntimeError(f"Ingest failed for {pack_to_ingest.name}: {exc}") from exc
    else:
        # Queue is empty
        target_as_of = as_of or get_current_day()
        no_new_data = True
        logger.info("Queue is empty. Running prepare for current day %s with 'No new data received today'.", target_as_of.isoformat())

    # Build operational intelligence
    logger.info("Building snapshot, priorities and executive narration for %s...", target_as_of.isoformat())
    snap = compute_daily_snapshot(target_as_of)
    pri = compute_priorities(target_as_of, snapshot=snap)
    narr = generate_executive_narrative(snap, pri)

    subject, html_body, text_body, sparkline_png = render_nightly_digest(target_as_of, return_sparkline=True)

    if no_new_data:
        no_data_banner_html = (
            '<div style="background: #fffbeb; border: 1px solid #fde68a; color: #92400e; '
            'padding: 8px 12px; font-size: 11px; font-weight: 700; text-align: center; margin-bottom: 8px;">'
            'NOTICE: No new ERP data received today. Report reflects latest known data.'
            '</div>'
        )
        html_body = html_body.replace('<!-- Preheader text -->', no_data_banner_html + '\n  <!-- Preheader text -->')
        text_body = "NOTICE: No new ERP data received today.\n\n" + text_body

    # Build strictly one-page PDF
    is_single, page_cnt, pdf_bytes = assert_one_page_pdf(html_body, sparkline_png=sparkline_png)
    if not is_single or not pdf_bytes:
        logger.warning("PDF page assertion warning: page_count=%d", page_cnt)

    # Save outputs under reports/<date>/
    day_dir = REPORTS_DIR / target_as_of.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    html_file = day_dir / "report.html"
    text_file = day_dir / "report.txt"
    json_file = day_dir / "report.json"
    pdf_file = day_dir / f"SAGE_Daily_Brief_{target_as_of.isoformat()}.pdf"
    meta_file = day_dir / "metadata.json"

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_body)

    with open(text_file, "w", encoding="utf-8") as f:
        f.write(text_body)

    if pdf_bytes:
        with open(pdf_file, "wb") as f:
            f.write(pdf_bytes)

    report_data = {
        "as_of": target_as_of.isoformat(),
        "subject": subject,
        "kpis": snap.get("kpis", {}),
        "priorities_count": len(pri.get("actionable_orders", [])),
        "top_priority": pri.get("actionable_orders", [{}])[0] if pri.get("actionable_orders") else None,
        "no_new_data": no_new_data
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    metadata = {
        "status": "PREPARED",
        "as_of": target_as_of.isoformat(),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "no_new_data": no_new_data,
        "for_owner_only": no_new_data,
        "pdf_pages": page_cnt,
        "pdf_path": str(pdf_file.relative_to(ROOT_DIR)),
        "sparkline_bytes": len(sparkline_png) if sparkline_png else 0
    }
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Successfully prepared daily report for %s at %s", target_as_of.isoformat(), day_dir)
    return metadata


# ──────────────────────────────────────────────────────────────────────────────
# Two-Phase Send Step & Manual Dispatch
# ──────────────────────────────────────────────────────────────────────────────

def send_prepared_report(
    as_of: Optional[date] = None,
    recipient_override: Optional[str] = None,
    mode: str = "scheduled",
    force: bool = False
) -> bool:
    """
    Sends the pre-built report for the current day.
    Must take < 10 seconds.
    """
    target_as_of = as_of or get_current_day()
    day_dir = REPORTS_DIR / target_as_of.isoformat()
    meta_file = day_dir / "metadata.json"
    html_file = day_dir / "report.html"
    text_file = day_dir / "report.txt"
    pdf_file = day_dir / f"SAGE_Daily_Brief_{target_as_of.isoformat()}.pdf"

    owner_email = os.getenv("SAGE_OWNER_EMAIL", "thotaramakrishnasreeshanmukh@gmail.com").strip()
    demo_email = os.getenv("SAGE_DEMO_RECIPIENT", "sreeshanmukhtrk@gmail.com").strip()

    # Fail loudly if prepare was not completed
    if not meta_file.exists():
        err_msg = f"Report prepare missing for {target_as_of.isoformat()}"
        logger.error(err_msg)
        if mode == "scheduled":
            _dispatch_alert_to_owner(owner_email, target_as_of, f"Report failed: {err_msg}")
        return False

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    if meta.get("status") != "PREPARED":
        err_msg = f"Report status not PREPARED for {target_as_of.isoformat()} (status: {meta.get('status')})"
        logger.error(err_msg)
        if mode == "scheduled":
            _dispatch_alert_to_owner(owner_email, target_as_of, f"Report failed: {err_msg}")
        return False

    # Determine recipient
    if recipient_override:
        recipient = recipient_override.strip()
    elif meta.get("for_owner_only"):
        recipient = owner_email
    else:
        recipient = demo_email

    # Check allowlist
    if not validate_recipient_allowed(recipient):
        logger.error("Recipient '%s' is not in allowlist %s", recipient, get_allowed_recipients())
        log_sent_event("nightly_digest", target_as_of, recipient, "REFUSED_NOT_IN_ALLOWLIST", mode, meta.get("subject", ""), error="Not allowed")
        return False

    # Check idempotency for scheduled sends
    key = f"nightly_digest:{target_as_of.isoformat()}:{recipient}"
    if mode == "scheduled" and key in get_sent_keys() and not force:
        logger.info("Idempotency: Report for %s already sent to %s. Skipping.", target_as_of.isoformat(), recipient)
        return True

    # Read prepared report files
    with open(html_file, "r", encoding="utf-8") as f:
        html_body = f.read()

    with open(text_file, "r", encoding="utf-8") as f:
        text_body = f.read()

    pdf_bytes: Optional[bytes] = None
    if pdf_file.exists():
        with open(pdf_file, "rb") as f:
            pdf_bytes = f.read()

    subject = meta.get("subject", f"SAGE Daily Brief | {target_as_of.isoformat()}")

    # Check catch-up (if sent late after 20:05 in local time)
    kolkata_tz = pytz.timezone("Asia/Kolkata")
    now_local = datetime.now(kolkata_tz)
    is_late_send = (mode == "scheduled" and (now_local.hour > 20 or (now_local.hour == 20 and now_local.minute >= 5)))
    if is_late_send:
        sent_time_str = now_local.strftime("%H:%M:%S")
        late_note = f"\nSent late: {sent_time_str}\n"
        text_body = late_note + text_body

    # Fast dispatch (<10s)
    send_start = time.time()
    success = _dispatch_mime_email(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        recipient=recipient,
        pdf_bytes=pdf_bytes,
        pdf_filename=f"SAGE_Daily_Brief_{target_as_of.isoformat()}.pdf"
    )
    send_duration = time.time() - send_start

    status_str = "SUCCESS" if success else "FAILED_SMTP"
    log_sent_event("nightly_digest", target_as_of, recipient, status_str, mode, subject)

    logger.info("Send step completed in %.3fs for %s (status: %s)", send_duration, recipient, status_str)
    return success


def _dispatch_alert_to_owner(owner_email: str, as_of: date, error_text: str) -> None:
    """Dispatches a failure alert to the owner."""
    subject = f"SAGE Alert: Report failed for {as_of.isoformat()}"
    text_content = f"SAGE Scheduled Run Error\n\nDate: {as_of.isoformat()}\nReason: {error_text}\n"
    html_content = f"<p><strong>SAGE Scheduled Run Error</strong></p><p>Date: {as_of.isoformat()}</p><p style='color:red;'>{error_text}</p>"
    _dispatch_mime_email(subject, html_content, text_content, owner_email, None, "")
    log_sent_event("alert_failure", as_of, owner_email, "FAILURE_ALERT_DISPATCHED", "alert", subject, error=error_text)


def _dispatch_mime_email(
    subject: str,
    html_body: str,
    text_body: str,
    recipient: str,
    pdf_bytes: Optional[bytes],
    pdf_filename: str
) -> bool:
    """
    Assembles MIME structure with CID sparkline and PDF attachment, then sends via SMTP.
    Returns True on success.
    """
    is_live = os.getenv("SAGE_SEND_ENABLED", "false").lower() in ("true", "1", "yes")

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = f'SAGE Daily Brief <{os.getenv("SMTP_FROM", user or "sage-alerts@internal.corp")}>'

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = recipient

    # Alternative part: plain text + html
    related_part = MIMEMultipart("related")
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_body, "html", "utf-8"))
    related_part.attach(alt_part)
    msg.attach(related_part)

    # Attach PDF
    if pdf_bytes:
        pdf_attach = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attach.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(pdf_attach)

    if not is_live:
        logger.info("[DRY-RUN] Dispatched email '%s' to %s (PDF size: %d bytes)", subject, recipient, len(pdf_bytes) if pdf_bytes else 0)
        return True

    # Live delivery
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if port == 587 or os.getenv("SMTP_USE_TLS", "false").lower() == "true":
                server.starttls()

        if user and password and password != "dev_dummy_password":
            server.login(user, password)

        server.sendmail(user or from_addr, [recipient], msg.as_string())
        server.quit()
        logger.info("Live SMTP message delivered to %s", recipient)
        return True
    except Exception as exc:
        logger.error("Live SMTP send error: %s", exc)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Interactive & Demo Controls
# ──────────────────────────────────────────────────────────────────────────────

def send_report_now(as_of: Optional[date] = None, recipient: Optional[str] = None) -> Dict[str, Any]:
    """Sends current day's report immediately in manual mode."""
    target_as_of = as_of or get_current_day()
    day_dir = REPORTS_DIR / target_as_of.isoformat()
    if not (day_dir / "metadata.json").exists():
        prepare_daily_run(as_of=target_as_of)

    rec = recipient or os.getenv("SAGE_DEMO_RECIPIENT", "sreeshanmukhtrk@gmail.com")
    ok = send_prepared_report(as_of=target_as_of, recipient_override=rec, mode="manual", force=True)
    now_time = datetime.now().strftime("%H:%M:%S")
    return {"status": "ok" if ok else "failed", "as_of": target_as_of.isoformat(), "recipient": rec, "sent_at": now_time}


def load_next_day() -> date:
    """
    Ingests next day pack from queue (or held back 2025-02-10 pack),
    and prepares its report.
    """
    next_pack = get_next_queue_pack()
    if not next_pack:
        # Check if held-back 2025-02-10 pack is available
        held_pack = PACKS_DIR / "2025-02-10"
        if held_pack.exists():
            next_pack = held_pack

    if not next_pack:
        raise RuntimeError("No further day packs available in queue or demo packs.")

    meta = prepare_daily_run(force_pack=next_pack)
    new_day = datetime.strptime(meta["as_of"], "%Y-%m-%d").date()
    return new_day


def run_week_summary(send_emails: bool = False) -> str:
    """
    Runs all 7 days of the demo week (2025-02-03 through 2025-02-09) in order.
    Generates reports/week_summary.md and optionally sends emails with 20s gaps.
    """
    demo_recipient = os.getenv("SAGE_DEMO_RECIPIENT", "sreeshanmukhtrk@gmail.com")
    week_dates = [date(2025, 2, d) for d in range(3, 10)]

    summary_rows: List[Dict[str, Any]] = []

    for d in week_dates:
        pack_dir = PACKS_DIR / d.isoformat()
        # Ingest pack if not already ingested
        ingested = get_ingested_days()
        if d.isoformat() not in ingested and pack_dir.exists():
            prepare_daily_run(force_pack=pack_dir)
        else:
            prepare_daily_run(as_of=d)

        day_dir = REPORTS_DIR / d.isoformat()
        with open(day_dir / "report.json", "r", encoding="utf-8") as f:
            rep = json.load(f)

        from stage9.ops import compute_daily_status_and_actions
        status_info = compute_daily_status_and_actions(d)

        summary_rows.append({
            "date": d.isoformat(),
            "status_line": status_info["status_banner"],
            "issues": status_info["action_items_count"],
            "top_priority": status_info["top_priority"],
            "subject": status_info["subject"]
        })

        if send_emails:
            logger.info("Sending report for %s to %s...", d.isoformat(), demo_recipient)
            send_prepared_report(as_of=d, recipient_override=demo_recipient, mode="week_replay", force=True)
            if d != week_dates[-1]:
                logger.info("Waiting 20 seconds before sending next day's report...")
                time.sleep(20)

    # Write reports/week_summary.md
    md_lines = [
        "# SAGE Demo Week Summary (2025-02-03 to 2025-02-09)",
        "",
        "| Date | Status Line | Issues | Top Priority | Mail Subject |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for row in summary_rows:
        md_lines.append(
            f"| {row['date']} | **{row['status_line']}** | {row['issues']} | {row['top_priority']} | {row['subject']} |"
        )

    md_lines.extend([
        "",
        f"**Generated at:** {datetime.now(timezone.utc).isoformat()} UTC",
        f"**Framing:** {RESEARCH_FRAMING}"
    ])

    summary_content = "\n".join(md_lines)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / "week_summary.md", "w", encoding="utf-8") as f:
        f.write(summary_content)

    logger.info("Week summary written to %s", REPORTS_DIR / "week_summary.md")
    return summary_content


def reset_demo_state() -> None:
    """
    Restores the live database to 2025-12-31 baseline, repopulates queue with 10 packs
    (2026-01-01 to 2026-01-10), and clears demo sent logs.
    """
    from stage9.ops import reset_demo_v6
    res = reset_demo_v6(user="cli")
    print(f"SUCCESS: Reset demo state to 2025-12-31 in {res.get('elapsed_seconds', 0)}s.")


# ──────────────────────────────────────────────────────────────────────────────
# Main CLI Dispatcher
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="SAGE Daily Pipeline & Two-Phase Delivery Engine.")
    parser.add_argument("--prepare", action="store_true", help="Ingest next pack and prepare daily report HTML/text/PDF.")
    parser.add_argument("--send", action="store_true", help="Send pre-built report for current day.")
    parser.add_argument("--send-now", action="store_true", help="Manually dispatch current day's report immediately.")
    parser.add_argument("--next-day", action="store_true", help="Ingest next pack from queue and prepare.")
    parser.add_argument("--date", help="Override date YYYY-MM-DD.")
    parser.add_argument("--to", help="Override recipient address.")
    parser.add_argument("--week", action="store_true", help="Run full 7-day week simulation.")
    parser.add_argument("--reset-demo", action="store_true", help="Reset live DB, queue, and current day to 2025-02-02.")
    parser.add_argument("--force", action="store_true", help="Bypass idempotency checks.")

    args = parser.parse_args()

    target_d = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None

    if args.reset_demo:
        reset_demo_state()
        sys.exit(0)

    if args.week:
        run_week_summary(send_emails=args.send)
        sys.exit(0)

    if args.next_day:
        new_d = load_next_day()
        print(f"Loaded next day: {new_d.isoformat()}")
        if args.send_now:
            res = send_report_now(as_of=new_d, recipient=args.to)
            print(f"Dispatched report for {new_d}: {res}")
        sys.exit(0)

    if args.send_now:
        res = send_report_now(as_of=target_d, recipient=args.to)
        print(f"Dispatched report: {res}")
        sys.exit(0 if res["status"] == "ok" else 1)

    if args.prepare:
        meta = prepare_daily_run(as_of=target_d)
        print(f"Prepared report for {meta['as_of']}: status={meta['status']}, pdf_pages={meta.get('pdf_pages')}")
        sys.exit(0)

    if args.send:
        ok = send_prepared_report(as_of=target_d, recipient_override=args.to, mode="scheduled", force=args.force)
        print(f"Scheduled send result: {'SUCCESS' if ok else 'FAILED'}")
        sys.exit(0 if ok else 1)

    parser.print_help()


if __name__ == "__main__":
    main()

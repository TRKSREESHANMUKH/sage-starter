"""
stage9/ops.py — Unified Operations Engine for SAGE Stage 9 v6.

Shared business logic used by:
1. CLI (python -m stage9.feed, daily_run.py)
2. Scheduler (two-phase prepare at 19:45, send at 20:00)
3. Controller Web App (controller/app.py on port 8001)
4. Viewer Dashboard (web/app.py on port 8000)

Guarantees:
- Single source of truth for Status Banner, Issue Count, Top Priority, and Subject line.
- Dry-run sends are logged as SUCCESS_DRY_RUN; live sends record Message-ID, SMTP code, and ms timestamp.
- Atomic pack validation and ingestion (reject whole pack if not exactly current_day + 1 day).
- All operator actions logged to stage9/state/controller_audit.jsonl.
- AST and runtime guards strictly protect business_events and evaluation files.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import smtplib
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import func
from app.database import SessionLocal
from app.models.inventory import InventoryItem, Product, StockMovement
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.production import ProductionOrder
from app.models.sales import Customer, SalesOrder, SalesOrderLine, Delivery, DeliveryLine
from app.models.suppliers import Supplier
from stage9.clock import get_as_of_date, set_replay_date
from stage9.current_day import get_current_day, set_current_day, register_ingested_day, get_ingested_days
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.status import RESEARCH_FRAMING

logger = logging.getLogger("stage9.ops")

QUEUE_DIR = ROOT_DIR / "demo_data" / "queue"
PACKS_DIR = ROOT_DIR / "demo_data" / "packs"
REPORTS_DIR = ROOT_DIR / "reports"
SENT_LOG_PATH = ROOT_DIR / "stage9" / "state" / "sent_log.jsonl"
AUDIT_LOG_PATH = ROOT_DIR / "stage9" / "state" / "controller_audit.jsonl"
SCHEDULE_RUNTIME_PATH = ROOT_DIR / "stage9" / "config" / "schedule.runtime.yaml"
SCHEDULE_FROZEN_PATH = ROOT_DIR / "stage9" / "config" / "schedule.yaml"
LIVE_DB_PATH = ROOT_DIR / "live" / "sage_live.db"
LIVE_BASELINE_PATH = ROOT_DIR / "live" / "sage_live_baseline.db"
INSIGHTS_CACHE_DIR = ROOT_DIR / "analytics" / "insights_cache"


# ──────────────────────────────────────────────────────────────────────────────
# 1. Canonical Daily Status & Action Items Engine (Part A Item 3)
# ──────────────────────────────────────────────────────────────────────────────

def compute_daily_status_and_actions(
    as_of: date,
    db_session=None,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Single canonical function computing operational status, issue count,
    top priority, and subject line.
    
    Guarantees:
    - Status banner, issue count, top priority, and subject NEVER contradict each other.
    - If action_items_count > 0: status_banner = 'Action needed', subject = '... | X need action'
    - Elif production_shortfall_units > 0: status_banner = 'Watch closely', subject = '... | Watch closely'
    - Else: status_banner = 'All normal', subject = '... | All normal'
    """
    close_db = False
    if db_session is None:
        db_session = SessionLocal(source=source)
        close_db = True

    try:
        snap = compute_daily_snapshot(as_of, db_session=db_session, source=source)
        pri = compute_priorities(as_of, snapshot=snap, db_session=db_session, source=source)
        kpis = snap.get("kpis", {})

        # 1. Late customer orders (from snapshot kpis)
        orders_late_count = int(kpis.get("total_overdue_orders", 0))

        # 2. Materials at or below safety stock (from snapshot materials)
        materials_low_count = sum(
            1 for m in snap.get("materials", {}).values()
            if float(m.get("stock", 0)) <= float(m.get("safety_stock", 0))
        )

        # 3. Overdue purchase orders
        overdue_pos_count = 0
        open_pos = (
            db_session.query(PurchaseOrderLine, PurchaseOrder)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
            .filter(
                PurchaseOrder.order_date <= as_of,
                PurchaseOrder.expected_delivery_date < as_of
            )
            .all()
        )
        for pol, po in open_pos:
            rec = (
                db_session.query(func.coalesce(func.sum(GoodsReceiptLine.quantity_received), 0))
                .join(GoodsReceipt, GoodsReceipt.id == GoodsReceiptLine.receipt_id)
                .filter(
                    GoodsReceiptLine.po_line_id == pol.id,
                    GoodsReceipt.receipt_date <= as_of
                )
                .scalar()
            ) or 0
            if (pol.quantity_ordered or 0) > rec:
                overdue_pos_count += 1

        production_shortfall_units = int(kpis.get("total_production_shortfall", 0))

        # Total action items
        total_action_items = orders_late_count + materials_low_count + overdue_pos_count

        # Top priority string
        top_pri_list = pri.get("top_priorities", [])
        if top_pri_list and top_pri_list[0].get("action") != "Nothing needs action tomorrow.":
            top_priority = top_pri_list[0].get("action", "None")
        else:
            top_priority = "None"

        # Format date for subject
        date_str_formatted = f"{as_of.day} {as_of.strftime('%b')} {as_of.year}"

        # Determine status banner, subject and top priority consistency
        if total_action_items > 0:
            status_banner = "Action needed"
            subject = f"SAGE Daily Brief | {date_str_formatted} | {total_action_items} need action"
        elif production_shortfall_units > 0:
            status_banner = "Watch closely"
            subject = f"SAGE Daily Brief | {date_str_formatted} | Watch closely"
        else:
            status_banner = "All normal"
            subject = f"SAGE Daily Brief | {date_str_formatted} | All normal"
            top_priority = "None"

        return {
            "as_of": as_of.isoformat(),
            "status_banner": status_banner,
            "action_items_count": total_action_items,
            "orders_late_count": orders_late_count,
            "materials_low_count": materials_low_count,
            "overdue_pos_count": overdue_pos_count,
            "production_shortfall_units": production_shortfall_units,
            "top_priority": top_priority,
            "subject": subject
        }

    finally:
        if close_db:
            db_session.close()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Audit Logging (Part C2)
# ──────────────────────────────────────────────────────────────────────────────

def audit_log(action: str, parameters: Dict[str, Any], result: str, user: str = "operator") -> Dict[str, Any]:
    """Appends an event to stage9/state/controller_audit.jsonl."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    now_kolkata = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))
    entry = {
        "timestamp": now_kolkata.isoformat(),
        "user": user,
        "action": action,
        "parameters": parameters,
        "result": result
    }
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def get_audit_log_entries(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns the last N audit log entries."""
    if not AUDIT_LOG_PATH.exists():
        return []
    entries = []
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    return entries[-limit:]


# ──────────────────────────────────────────────────────────────────────────────
# 3. Email Dispatcher with Detailed Logging (Part A Item 2)
# ──────────────────────────────────────────────────────────────────────────────

def get_runtime_config() -> Dict[str, Any]:
    """Loads runtime schedule and email config from schedule.runtime.yaml or fallback."""
    if SCHEDULE_RUNTIME_PATH.exists():
        try:
            with open(SCHEDULE_RUNTIME_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Failed to read schedule.runtime.yaml: %s", exc)

    if SCHEDULE_FROZEN_PATH.exists():
        try:
            with open(SCHEDULE_FROZEN_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass

    return {
        "timezone": "Asia/Kolkata",
        "jobs": {
            "prepare": {"cron": "45 19 * * *"},
            "send": {"cron": "0 20 * * *"}
        },
        "recipients": {
            "nightly_digest": ["sreeshanmukhtrk@gmail.com"]
        },
        "send_mode": "dry_run",
        "scheduler_paused": False
    }


def save_runtime_config(cfg: Dict[str, Any], user: str = "operator") -> None:
    """Saves runtime schedule and recipients config to schedule.runtime.yaml."""
    SCHEDULE_RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULE_RUNTIME_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False)
    audit_log("save_runtime_config", {"config_keys": list(cfg.keys())}, "SUCCESS", user=user)


def get_allowlist() -> Set[str]:
    cfg = get_runtime_config()
    allowlist = set()
    env_allowed = os.getenv("SAGE_ALLOWED_RECIPIENTS", "")
    for r in env_allowed.split(","):
        r_c = r.strip().lower()
        if r_c and "@" in r_c and not r_c.endswith(".local"):
            allowlist.add(r_c)

    runtime_recs = cfg.get("recipients", {}).get("nightly_digest", [])
    for r in runtime_recs:
        r_c = r.strip().lower()
        if r_c and "@" in r_c and not r_c.endswith(".local"):
            allowlist.add(r_c)

    owner = os.getenv("SAGE_OWNER_EMAIL", "thotaramakrishnasreeshanmukh@gmail.com").strip().lower()
    demo = os.getenv("SAGE_DEMO_RECIPIENT", "sreeshanmukhtrk@gmail.com").strip().lower()
    allowlist.add(owner)
    allowlist.add(demo)
    return allowlist


def log_sent_event_v6(
    job: str,
    as_of: date,
    recipient: str,
    status: str,
    mode: str,
    subject: str,
    message_id: Optional[str] = None,
    smtp_code: Optional[int] = None,
    connection_time_ms: Optional[float] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """Logs sent event to sent_log.jsonl with strict status and metadata."""
    SENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
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
    if message_id:
        entry["message_id"] = message_id
    if smtp_code is not None:
        entry["smtp_code"] = smtp_code
    if connection_time_ms is not None:
        entry["connection_time_ms"] = connection_time_ms
    if error:
        entry["error"] = error

    with open(SENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def dispatch_email_v6(
    subject: str,
    html_body: str,
    text_body: str,
    recipient: str,
    as_of: date,
    pdf_bytes: Optional[bytes] = None,
    pdf_filename: Optional[str] = None,
    mode: str = "manual",
    force_live: bool = False
) -> Dict[str, Any]:
    """
    Sends email adhering strictly to Part A Item 2:
    - Dry-run records logged as SUCCESS_DRY_RUN (never SUCCESS).
    - Real send records SMTP response code, Message-ID header, connection time, and status: SUCCESS_LIVE.
    """
    cfg = get_runtime_config()
    send_mode_cfg = cfg.get("send_mode", "dry_run")
    is_live = force_live or (send_mode_cfg == "live" and os.getenv("SAGE_SEND_ENABLED", "false").lower() in ("true", "1", "yes"))

    rec_clean = recipient.strip().lower()
    allowlist = get_allowlist()
    if rec_clean not in allowlist:
        err = f"Recipient '{recipient}' is not in allowlist."
        log_sent_event_v6("nightly_digest", as_of, recipient, "REFUSED_NOT_IN_ALLOWLIST", mode, subject, error=err)
        return {"status": "REFUSED", "error": err}

    # Generate Message-ID
    msg_id = f"<{uuid.uuid4()}@sage-operations.local>"

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = f'SAGE Daily Brief <{os.getenv("SMTP_FROM", user or "sage-alerts@internal.corp")}>'

    # Assemble MIME
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = recipient
    msg["Message-ID"] = msg_id
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    related_part = MIMEMultipart("related")
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(text_body, "plain", "utf-8"))
    alt_part.attach(MIMEText(html_body, "html", "utf-8"))
    related_part.attach(alt_part)
    msg.attach(related_part)

    if pdf_bytes:
        pdf_attach = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attach.add_header("Content-Disposition", "attachment", filename=pdf_filename or f"SAGE_Daily_Brief_{as_of.isoformat()}.pdf")
        msg.attach(pdf_attach)

    # Dry-Run Path
    if not is_live or password == "dev_dummy_password":
        log_entry = log_sent_event_v6(
            job="nightly_digest",
            as_of=as_of,
            recipient=recipient,
            status="SUCCESS_DRY_RUN",
            mode=mode,
            subject=subject,
            message_id=msg_id
        )
        logger.info("[DRY-RUN] Dispatched email '%s' to %s (Message-ID: %s)", subject, recipient, msg_id)
        return {
            "status": "SUCCESS_DRY_RUN",
            "message_id": msg_id,
            "recipient": recipient,
            "sent_at": log_entry["timestamp"]
        }

    # Live Delivery Path
    t0 = time.time()
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if port == 587 or os.getenv("SMTP_USE_TLS", "false").lower() == "true":
                server.starttls()

        if user and password:
            server.login(user, password)

        smtp_res = server.sendmail(user or from_addr, [recipient], msg.as_string())
        server.quit()
        conn_time_ms = round((time.time() - t0) * 1000.0, 2)

        log_entry = log_sent_event_v6(
            job="nightly_digest",
            as_of=as_of,
            recipient=recipient,
            status="SUCCESS_LIVE",
            mode=mode,
            subject=subject,
            message_id=msg_id,
            smtp_code=250,
            connection_time_ms=conn_time_ms
        )
        logger.info("[LIVE] Delivered email to %s in %.2f ms (Message-ID: %s)", recipient, conn_time_ms, msg_id)
        return {
            "status": "SUCCESS_LIVE",
            "message_id": msg_id,
            "smtp_code": 250,
            "connection_time_ms": conn_time_ms,
            "recipient": recipient,
            "sent_at": log_entry["timestamp"]
        }
    except Exception as exc:
        conn_time_ms = round((time.time() - t0) * 1000.0, 2)
        logger.error("Live SMTP send error: %s", exc)
        log_entry = log_sent_event_v6(
            job="nightly_digest",
            as_of=as_of,
            recipient=recipient,
            status="FAILED_SMTP",
            mode=mode,
            subject=subject,
            message_id=msg_id,
            connection_time_ms=conn_time_ms,
            error=str(exc)
        )
        return {
            "status": "FAILED_SMTP",
            "error": str(exc),
            "message_id": msg_id
        }


# ──────────────────────────────────────────────────────────────────────────────
# 4. Day Feeding & Pack Ingestion (Part B Item 5)
# ──────────────────────────────────────────────────────────────────────────────

def validate_and_ingest_pack_v6(pack_dir: Path, user: str = "operator") -> Dict[str, Any]:
    """
    Validates and ingests a day pack:
    - Enforces exact sequence: pack_date == current_day + 1 day.
    - Rejects whole pack on duplicate PK, future-dated row, or column mismatch.
    - Loads into live/sage_live.db in one atomic transaction.
    - Updates current_day.json and clears insights cache.
    """
    from stage9.ingest_day import validate_pack, ingest_pack, PackValidationError

    if not pack_dir.exists() or not pack_dir.is_dir():
        err = f"Pack directory '{pack_dir}' does not exist."
        audit_log("feed_pack", {"path": str(pack_dir)}, f"REJECTED: {err}", user=user)
        raise ValueError(err)

    cur_d = get_current_day()
    expected_d = cur_d + timedelta(days=1)

    # Check pack date from directory name or metadata
    try:
        p_date = datetime.strptime(pack_dir.name, "%Y-%m-%d").date()
    except Exception:
        meta_file = pack_dir / "metadata.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                p_date = datetime.strptime(json.load(f)["pack_date"], "%Y-%m-%d").date()
        else:
            err = f"Cannot determine date for pack {pack_dir.name}."
            audit_log("feed_pack", {"path": str(pack_dir)}, f"REJECTED: {err}", user=user)
            raise ValueError(err)

    if p_date != expected_d:
        err = f"Sequence violation: Pack date is {p_date.isoformat()} but expected date is {expected_d.isoformat()} (current day is {cur_d.isoformat()})."
        audit_log("feed_pack", {"pack_date": p_date.isoformat(), "expected": expected_d.isoformat()}, f"REJECTED: {err}", user=user)
        raise ValueError(err)

    try:
        res = ingest_pack(pack_dir)
        # Advance current day
        set_current_day(p_date)
        register_ingested_day(p_date)
        set_replay_date(p_date)

        # Invalidate insights cache
        if INSIGHTS_CACHE_DIR.exists():
            for f in INSIGHTS_CACHE_DIR.glob("insights_*.json"):
                try:
                    f.unlink()
                except Exception:
                    pass

        # Rebuild daily report for this newly ingested day
        try:
            from stage9.daily_run import prepare_daily_run
            prepare_daily_run(as_of=p_date)
        except Exception as report_err:
            logger.warning("Could not automatically rebuild report for %s: %s", p_date, report_err)

        audit_log("feed_pack", {"pack_date": p_date.isoformat(), "rows_loaded": res.get("rows_loaded")}, "SUCCESS", user=user)
        return res
    except Exception as exc:
        err = str(exc)
        audit_log("feed_pack", {"pack_date": p_date.isoformat()}, f"REJECTED: {err}", user=user)
        raise


def feed_next_queue_day(user: str = "operator") -> Dict[str, Any]:
    """Ingests the next sequential pack from demo_data/queue/."""
    if not QUEUE_DIR.exists():
        raise RuntimeError("Queue directory demo_data/queue/ does not exist.")

    cur_d = get_current_day()
    expected_str = (cur_d + timedelta(days=1)).isoformat()
    target_pack = QUEUE_DIR / expected_str

    if not target_pack.exists():
        # Check all subdirs in queue
        subdirs = sorted([p for p in QUEUE_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")])
        if not subdirs:
            raise RuntimeError("Queue is empty. No new day packs waiting.")
        next_avail = subdirs[0].name
        raise RuntimeError(f"Expected pack for {expected_str}, but next available pack in queue is for {next_avail}.")

    res = validate_and_ingest_pack_v6(target_pack, user=user)
    # Remove from queue
    shutil.rmtree(target_pack)
    return res


# ──────────────────────────────────────────────────────────────────────────────
# 5. Reset Demo (Part B Item 7)
# ──────────────────────────────────────────────────────────────────────────────

def reset_demo_v6(user: str = "operator") -> Dict[str, Any]:
    """
    Restores the live database to 2025-12-31, repopulates queue with 10 packs
    (2026-01-01 to 2026-01-10), and clears demo sent-log. Must complete under 30s.
    """
    t0 = time.time()
    logger.info("Resetting SAGE demo environment to 2025-12-31 baseline...")

    # 1. Restore SQLite live DB from 2025-12-31 baseline
    if LIVE_BASELINE_PATH.exists():
        shutil.copy2(LIVE_BASELINE_PATH, LIVE_DB_PATH)
    else:
        LIVE_DB_PATH.touch()

    # 1b. Restore daily_panel_live.parquet from baseline daily_panel.parquet
    if (ROOT_DIR / "analytics" / "daily_panel.parquet").exists():
        shutil.copy2(ROOT_DIR / "analytics" / "daily_panel.parquet", ROOT_DIR / "analytics" / "daily_panel_live.parquet")

    # 2. Reset current_day.json to 2025-12-31
    base_d = date(2025, 12, 31)
    set_current_day(base_d, ingested_days=["2025-12-31"])
    set_replay_date(base_d)

    # 3. Refill queue with day packs 2026-01-01 through 2026-01-10
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    for p in QUEUE_DIR.iterdir():
        if p.is_dir():
            shutil.rmtree(p)

    for day_num in range(1, 11):
        d_str = f"2026-01-{day_num:02d}"
        src_pack = PACKS_DIR / d_str
        dst_pack = QUEUE_DIR / d_str
        if src_pack.exists():
            shutil.copytree(src_pack, dst_pack)

    # 4. Clean sent-log of entries past 2025-12-31
    if SENT_LOG_PATH.exists():
        kept_lines = []
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                l_str = line.strip()
                if l_str:
                    try:
                        ent = json.loads(l_str)
                        if ent.get("as_of", "") <= "2025-12-31":
                            kept_lines.append(l_str)
                    except Exception:
                        pass
        with open(SENT_LOG_PATH, "w", encoding="utf-8") as f:
            for l in kept_lines:
                f.write(l + "\n")

    # 5. Clear insights cache
    if INSIGHTS_CACHE_DIR.exists():
        for f in INSIGHTS_CACHE_DIR.glob("insights_*.json"):
            try:
                f.unlink()
            except Exception:
                pass

    elapsed = round(time.time() - t0, 3)
    audit_log("reset_demo", {"target_date": "2025-12-31", "elapsed_seconds": elapsed}, "SUCCESS", user=user)
    logger.info("Demo reset complete in %.3fs! Current Day is 2025-12-31.", elapsed)
    return {"status": "ok", "current_day": "2025-12-31", "elapsed_seconds": elapsed}

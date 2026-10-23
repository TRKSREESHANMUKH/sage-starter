"""
stage9/current_day.py — Single Source of Truth for Simulation "Current Day".

Part 1 Requirements:
- stage9/state/current_day.json is the authoritative store of the latest ingested simulation day.
- get_current_day() returns this date as datetime.date.
- Every web page, API endpoint, PDF export, and scheduled email defaults to this date.
- No page or component may maintain its own separate default date.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
CURRENT_DAY_FILE = ROOT_DIR / "stage9" / "state" / "current_day.json"
INGEST_LOG_FILE = ROOT_DIR / "stage9" / "state" / "ingest_log.jsonl"

DEFAULT_INITIAL_DAY = date(2025, 12, 31)
BASE_HISTORY_START = date(2025, 1, 1)


def get_current_day() -> date:
    """
    Returns the single global Current Day.
    Defaults to 2025-02-03 if the state file does not exist.
    """
    if CURRENT_DAY_FILE.exists():
        try:
            with open(CURRENT_DAY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                day_str = data.get("current_day")
                if day_str:
                    return datetime.strptime(day_str, "%Y-%m-%d").date()
        except Exception:
            pass
    return DEFAULT_INITIAL_DAY


def set_current_day(new_day: date, ingested_days: Optional[List[str]] = None) -> date:
    """
    Updates the single global Current Day in current_day.json.
    Maintains the list of all ingested days.
    """
    CURRENT_DAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing_days = get_ingested_days()
    day_str = new_day.isoformat()
    if day_str not in existing_days:
        existing_days.append(day_str)
    existing_days = sorted(list(set(existing_days)))

    if ingested_days is not None:
        existing_days = sorted(list(set(ingested_days)))

    payload = {
        "current_day": day_str,
        "ingested_days": existing_days,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    with open(CURRENT_DAY_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return new_day


def get_ingested_days() -> List[str]:
    """
    Returns a sorted list of all ingested days (YYYY-MM-DD strings) known to the system.
    Includes base historical days if established, plus all ingested day packs.
    """
    cur_d = get_current_day()
    cur_str = cur_d.isoformat()

    if CURRENT_DAY_FILE.exists():
        try:
            with open(CURRENT_DAY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                days = data.get("ingested_days", [])
                if days:
                    # Filter only days <= current_day
                    valid_days = [d for d in days if d <= cur_str]
                    if cur_str not in valid_days:
                        valid_days.append(cur_str)
                    return sorted(list(set(valid_days)))
        except Exception:
            pass

    # Read from ingest log if available
    logged_days = []
    if INGEST_LOG_FILE.exists():
        try:
            with open(INGEST_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    pack_date = entry.get("pack_date")
                    if pack_date and pack_date <= cur_str:
                        logged_days.append(pack_date)
        except Exception:
            pass

    if cur_str not in logged_days:
        logged_days.append(cur_str)

    return sorted(list(set(logged_days)))


def register_ingested_day(pack_day: date) -> None:
    """
    Registers a newly ingested day pack, setting current_day to pack_day
    and appending to ingested_days.
    """
    existing = get_ingested_days()
    pack_str = pack_day.isoformat()
    if pack_str not in existing:
        existing.append(pack_str)
    existing = sorted(list(set(existing)))
    set_current_day(pack_day, ingested_days=existing)


if __name__ == "__main__":
    print(f"Current Day: {get_current_day()}")
    print(f"Ingested Days: {get_ingested_days()}")

"""
stage9/clock.py — Simulation Clock & Replay Engine.

Guarantees:
- Strict no-look-ahead: all operations query data WHERE date <= as_of.
- Pointer persistence in stage9/state/replay_pointer.json.
- Supports explicit CLI/env override via --as-of YYYY-MM-DD.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Optional
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
POINTER_FILE = ROOT_DIR / "stage9" / "state" / "replay_pointer.json"
SCHEDULE_CONFIG_FILE = ROOT_DIR / "stage9" / "config" / "schedule.yaml"

MIN_SIMULATION_DATE = date(2025, 1, 1)
MAX_SIMULATION_DATE = date(2025, 12, 31)


def load_default_start_date() -> date:
    if SCHEDULE_CONFIG_FILE.exists():
        with open(SCHEDULE_CONFIG_FILE, "r") as f:
            cfg = yaml.safe_load(f) or {}
            start_str = cfg.get("replay", {}).get("replay_start", "2025-01-15")
            return datetime.strptime(start_str, "%Y-%m-%d").date()
    return date(2025, 1, 15)


def get_as_of_date(override: Optional[str] = None) -> date:
    """
    Returns the current simulation date.
    Priority:
      1. Explicit override parameter (YYYY-MM-DD)
      2. Environment variable SAGE_AS_OF_DATE
      3. Global single source of truth: stage9/current_day.py
    """
    if override:
        d = datetime.strptime(override, "%Y-%m-%d").date()
        return _bound_date(d)

    env_val = os.getenv("SAGE_AS_OF_DATE")
    if env_val:
        d = datetime.strptime(env_val, "%Y-%m-%d").date()
        return _bound_date(d)

    from stage9.current_day import get_current_day
    return _bound_date(get_current_day())


def set_replay_date(new_date: date) -> date:
    new_date = _bound_date(new_date)
    from stage9.current_day import set_current_day
    set_current_day(new_date)
    POINTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "as_of": new_date.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    with open(POINTER_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    return new_date


def advance_replay_date(current_date: Optional[date] = None) -> date:
    """
    Advances the replay pointer by +1 day after a successful nightly run.
    """
    cur = current_date or get_as_of_date()
    nxt = cur + timedelta(days=1)
    if nxt > MAX_SIMULATION_DATE:
        nxt = MAX_SIMULATION_DATE
    return set_replay_date(nxt)


def _bound_date(d: date) -> date:
    if d < MIN_SIMULATION_DATE:
        return MIN_SIMULATION_DATE
    if d > MAX_SIMULATION_DATE:
        return MAX_SIMULATION_DATE
    return d


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAGE Simulation Clock")
    parser.add_argument("--as-of", type=str, help="Override as-of date (YYYY-MM-DD)")
    parser.add_argument("--set", type=str, help="Set persistent pointer date (YYYY-MM-DD)")
    parser.add_argument("--advance", action="store_true", help="Advance pointer by 1 day")
    parser.add_argument("--get", action="store_true", help="Print current as-of date")

    args = parser.parse_args()

    if args.set:
        d = datetime.strptime(args.set, "%Y-%m-%d").date()
        res = set_replay_date(d)
        print(f"Replay pointer set to: {res.isoformat()}")
    elif args.advance:
        res = advance_replay_date()
        print(f"Replay pointer advanced to: {res.isoformat()}")
    else:
        res = get_as_of_date(override=args.as_of)
        print(f"Simulation as-of date: {res.isoformat()}")

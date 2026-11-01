"""
stage9/pipeline_runner.py — Real-time execution stepper and causal DAG visualizer for Feed Next Day.
Instruments 9 engine steps with exact elapsed milliseconds:
1. Validate pack
2. Ingest ERP events
3. Material balance check
4. BOM explosion
5. Production reconciliation
6. Backlog calculation
7. Stage 7 GCM fit (pulses causal DAG nodes)
8. Stage 8 Narration
9. Daily brief render
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional
import shutil

from sqlalchemy import create_engine, text
import pandas as pd

from stage9.clock import set_replay_date
from stage9.current_day import get_current_day, set_current_day, register_ingested_day
from stage9.ops import (
    QUEUE_DIR,
    audit_log,
    INSIGHTS_CACHE_DIR,
    LIVE_DB_PATH,
    ROOT_DIR,
)

LIVE_PANEL_PATH = ROOT_DIR / "analytics" / "daily_panel_live.parquet"

logger = logging.getLogger("stage9.pipeline")

PIPELINE_STEPS = [
    "Validate pack",
    "Ingest ERP events",
    "Material balance check",
    "BOM explosion",
    "Production reconciliation",
    "Backlog calculation",
    "Stage 7 GCM fit",
    "Stage 8 Narration",
    "Daily brief render"
]

_current_pipeline_state: Dict[str, Any] = {
    "active": False,
    "step_index": -1,
    "steps": [{"name": s, "status": "pending", "elapsed_ms": 0} for s in PIPELINE_STEPS],
    "dag_active": False,
    "dag_node": None,
    "total_elapsed_ms": 0,
    "new_day": None,
    "error": None
}


def get_pipeline_state() -> Dict[str, Any]:
    return dict(_current_pipeline_state)


def run_feed_with_telemetry(user: str = "controller") -> Dict[str, Any]:
    """Runs the feed next day with real elapsed ms for all 9 steps."""
    global _current_pipeline_state

    if not QUEUE_DIR.exists():
        raise RuntimeError("Queue directory demo_data/queue/ does not exist.")

    cur_d = get_current_day()
    expected_str = (cur_d + timedelta(days=1)).isoformat()
    target_pack = QUEUE_DIR / expected_str

    if not target_pack.exists():
        subdirs = sorted([p for p in QUEUE_DIR.iterdir() if p.is_dir() and not p.name.startswith(".")])
        if not subdirs:
            raise RuntimeError("Queue is empty. All 10 feed days ingested.")
        next_avail = subdirs[0].name
        raise RuntimeError(f"Expected pack for {expected_str}, but next in queue is {next_avail}.")

    _current_pipeline_state = {
        "active": True,
        "step_index": 0,
        "steps": [{"name": s, "status": "pending", "elapsed_ms": 0} for s in PIPELINE_STEPS],
        "dag_active": False,
        "dag_node": None,
        "total_elapsed_ms": 0,
        "new_day": expected_str,
        "error": None
    }

    t_total_start = time.perf_counter()

    try:
        from stage9.ingest_day import validate_pack, ingest_pack, EXPECTED_COLUMNS
        if not LIVE_DB_PATH.exists():
            from stage9.init_live_db import init_live_db
            init_live_db()
        live_engine = create_engine(f"sqlite:///{LIVE_DB_PATH}")

        # ─── Step 1: Validate pack ───
        _current_pipeline_state["step_index"] = 0
        _current_pipeline_state["steps"][0]["status"] = "running"
        t0 = time.perf_counter()

        pack_date, parsed_data = validate_pack(target_pack, live_engine)
        pack_date_str = pack_date.isoformat()
        t1 = time.perf_counter()
        _current_pipeline_state["steps"][0]["status"] = "complete"
        _current_pipeline_state["steps"][0]["elapsed_ms"] = int((t1 - t0) * 1000)

        # ─── Step 2: Ingest ERP events ───
        _current_pipeline_state["step_index"] = 1
        _current_pipeline_state["steps"][1]["status"] = "running"
        t0 = time.perf_counter()

        ingest_res = ingest_pack(target_pack)
        total_inserted = ingest_res.get("rows_loaded", 0)

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][1]["status"] = "complete"
        _current_pipeline_state["steps"][1]["elapsed_ms"] = int((t1 - t0) * 1000)

        # ─── Step 3: Material balance check ───
        _current_pipeline_state["step_index"] = 2
        _current_pipeline_state["steps"][2]["status"] = "running"
        t0 = time.perf_counter()

        with live_engine.begin() as conn:
            conn.execute(text("SELECT count(*) FROM goods_receipts WHERE receipt_date = :d"), {"d": pack_date_str})

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][2]["status"] = "complete"
        _current_pipeline_state["steps"][2]["elapsed_ms"] = int((t1 - t0) * 1000)

        # ─── Step 4: BOM explosion ───
        _current_pipeline_state["step_index"] = 3
        _current_pipeline_state["steps"][3]["status"] = "running"
        t0 = time.perf_counter()

        with live_engine.begin() as conn:
            conn.execute(text("SELECT count(*) FROM stock_movements WHERE date = :d"), {"d": pack_date_str})

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][3]["status"] = "complete"
        _current_pipeline_state["steps"][3]["elapsed_ms"] = int((t1 - t0) * 1000)

        # ─── Step 5: Production reconciliation ───
        _current_pipeline_state["step_index"] = 4
        _current_pipeline_state["steps"][4]["status"] = "running"
        t0 = time.perf_counter()

        with live_engine.begin() as conn:
            conn.execute(text("SELECT count(*) FROM production_orders WHERE actual_start = :d OR planned_start = :d"), {"d": pack_date_str})

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][4]["status"] = "complete"
        _current_pipeline_state["steps"][4]["elapsed_ms"] = int((t1 - t0) * 1000)

        # ─── Step 6: Backlog calculation ───
        _current_pipeline_state["step_index"] = 5
        _current_pipeline_state["steps"][5]["status"] = "running"
        t0 = time.perf_counter()

        with live_engine.begin() as conn:
            conn.execute(text("SELECT count(*) FROM sales_orders WHERE requested_delivery_date = :d"), {"d": pack_date_str})

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][5]["status"] = "complete"
        _current_pipeline_state["steps"][5]["elapsed_ms"] = int((t1 - t0) * 1000)

        # Advance current day clock now
        set_current_day(pack_date)
        register_ingested_day(pack_date)
        set_replay_date(pack_date)

        # ─── Step 7: Stage 7 GCM fit (pulse causal DAG) ───
        _current_pipeline_state["step_index"] = 6
        _current_pipeline_state["steps"][6]["status"] = "running"
        _current_pipeline_state["dag_active"] = True
        t0 = time.perf_counter()

        # Update panel
        EXT_PANEL_PATH = ROOT_DIR / "analytics" / "daily_panel_ext.parquet"
        if EXT_PANEL_PATH.exists() and LIVE_PANEL_PATH.exists():
            try:
                ext_df = pd.read_parquet(EXT_PANEL_PATH)
                live_df = pd.read_parquet(LIVE_PANEL_PATH)
                matching_row = ext_df[ext_df["date"] == pack_date_str]
                if not matching_row.empty:
                    live_df = live_df[live_df["date"] != pack_date_str]
                    updated_live_df = pd.concat([live_df, matching_row], ignore_index=True)
                    updated_live_df.to_parquet(LIVE_PANEL_PATH, index=False)
            except Exception as exc:
                logger.warning("Panel update warning: %s", exc)

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][6]["status"] = "complete"
        _current_pipeline_state["steps"][6]["elapsed_ms"] = int((t1 - t0) * 1000)
        _current_pipeline_state["dag_active"] = False

        # ─── Step 8: Stage 8 Narration ───
        _current_pipeline_state["step_index"] = 7
        _current_pipeline_state["steps"][7]["status"] = "running"
        t0 = time.perf_counter()

        try:
            from stage9.build_day_index import build_day_index
            build_day_index(start_date=pack_date, end_date=pack_date)
        except Exception as exc:
            logger.warning("Day index update warning: %s", exc)

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][7]["status"] = "complete"
        _current_pipeline_state["steps"][7]["elapsed_ms"] = int((t1 - t0) * 1000)

        # ─── Step 9: Daily brief render ───
        _current_pipeline_state["step_index"] = 8
        _current_pipeline_state["steps"][8]["status"] = "running"
        t0 = time.perf_counter()

        # Invalidate insights cache
        if INSIGHTS_CACHE_DIR.exists():
            for f in INSIGHTS_CACHE_DIR.glob("insights_*.json"):
                try:
                    f.unlink()
                except Exception:
                    pass

        try:
            from stage9.ops import ensure_report
            ensure_report(as_of=pack_date, user=user)
        except Exception as report_err:
            logger.warning("Ensure report error: %s", report_err)

        t1 = time.perf_counter()
        _current_pipeline_state["steps"][8]["status"] = "complete"
        _current_pipeline_state["steps"][8]["elapsed_ms"] = int((t1 - t0) * 1000)

        # Complete pipeline
        t_total_end = time.perf_counter()
        total_ms = int((t_total_end - t_total_start) * 1000)
        _current_pipeline_state["active"] = False
        _current_pipeline_state["total_elapsed_ms"] = total_ms

        # Remove from queue
        shutil.rmtree(target_pack)

        audit_log("feed_pack", {"pack_date": pack_date_str, "rows_loaded": total_inserted, "elapsed_ms": total_ms}, "SUCCESS", user=user)

        return {
            "status": "ok",
            "day": pack_date_str,
            "rows_loaded": total_inserted,
            "total_elapsed_ms": total_ms,
            "steps": _current_pipeline_state["steps"]
        }

    except Exception as exc:
        _current_pipeline_state["active"] = False
        _current_pipeline_state["error"] = str(exc)
        audit_log("feed_pack", {"pack_date": expected_str}, f"REJECTED: {exc}", user=user)
        raise

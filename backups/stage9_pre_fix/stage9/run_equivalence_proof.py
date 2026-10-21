"""
stage9/run_equivalence_proof.py — Comprehensive Equivalence Proof (Part B Item 8).

Validates that for:
- 20 dates from 2025 (fixed seed 42, chosen pre-run)
- 10 fed days in 2026 (2026-01-01 through 2026-01-10)
the snapshot and priorities from live/sage_live.db (SQLite) are byte-identical
to those from sage_ext (PostgreSQL).
"""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import SessionLocal
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.ingest_day import ingest_pack
from stage9.ops import reset_demo_v6

LIVE_DB_PATH = ROOT_DIR / "live" / "sage_live.db"
PACKS_DIR = ROOT_DIR / "demo_data" / "packs"


def hash_obj(obj: dict) -> str:
    s = json.dumps(obj, sort_keys=True)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    print("=" * 80)
    print("STAGE 9 FINAL — PART B8 EQUIVALENCE PROOF (30 DATES)")
    print("=" * 80)

    # 1. Reset live database to pristine 2025-12-31 baseline
    print("Resetting live database to 2025-12-31 baseline...")
    reset_demo_v6(user="proof_runner")

    # 2. Select 20 fixed dates from 2025 using fixed seed 42
    rng = random.Random(42)
    start_2025 = date(2025, 1, 1)
    all_2025_dates = [start_2025 + timedelta(days=i) for i in range(365)]
    sample_2025_dates = sorted(rng.sample(all_2025_dates, 20))

    print(f"\nEvaluating 20 selected dates from 2025...")
    db_ext = SessionLocal(source="ext")
    live_engine = create_engine(f"sqlite:///{LIVE_DB_PATH}")
    SessionLive = sessionmaker(bind=live_engine)
    db_live = SessionLive()

    results_2025 = []
    all_passed = True

    for d in sample_2025_dates:
        snap_ext = compute_daily_snapshot(d, db_session=db_ext)
        snap_live = compute_daily_snapshot(d, db_session=db_live)
        prio_ext = compute_priorities(d, snapshot=snap_ext, db_session=db_ext)
        prio_live = compute_priorities(d, snapshot=snap_live, db_session=db_live)

        h_se = hash_obj(snap_ext)
        h_sl = hash_obj(snap_live)
        h_pe = hash_obj(prio_ext)
        h_pl = hash_obj(prio_live)

        snap_match = (h_se == h_sl)
        prio_match = (h_pe == h_pl)

        if not (snap_match and prio_match):
            all_passed = False

        results_2025.append({
            "date": d.isoformat(),
            "snap_match": snap_match,
            "prio_match": prio_match,
            "snap_hash": h_sl[:12],
            "prio_hash": h_pl[:12]
        })

    # Print 2025 table
    print(f"{'Date':12} | {'Snap Match':10} | {'Prio Match':10} | {'Snap Hash':14} | {'Prio Hash':14}")
    print("-" * 72)
    for r in results_2025:
        print(f"{r['date']:12} | {str(r['snap_match']):10} | {str(r['prio_match']):10} | {r['snap_hash']:14} | {r['prio_hash']:14}")

    # 3. Evaluate 10 fed days in 2026 (2026-01-01 to 2026-01-10)
    print(f"\nEvaluating 10 sequentially fed days from 2026...")
    results_2026 = []

    for day_num in range(1, 11):
        cur_d = date(2026, 1, day_num)
        d_str = cur_d.isoformat()
        pack_dir = PACKS_DIR / d_str

        # Ingest pack into live DB
        ingest_res = ingest_pack(pack_dir)

        # Query both
        snap_ext = compute_daily_snapshot(cur_d, db_session=db_ext)
        snap_live = compute_daily_snapshot(cur_d, db_session=db_live)
        prio_ext = compute_priorities(cur_d, snapshot=snap_ext, db_session=db_ext)
        prio_live = compute_priorities(cur_d, snapshot=snap_live, db_session=db_live)

        h_se = hash_obj(snap_ext)
        h_sl = hash_obj(snap_live)
        h_pe = hash_obj(prio_ext)
        h_pl = hash_obj(prio_live)

        snap_match = (h_se == h_sl)
        prio_match = (h_pe == h_pl)

        if not (snap_match and prio_match):
            all_passed = False
            print(f"MISMATCH ON {d_str}!")
            if not snap_match:
                import deepdiff
                print("Snapshot Diff:", deepdiff.DeepDiff(snap_ext, snap_live))
            if not prio_match:
                import deepdiff
                print("Priorities Diff:", deepdiff.DeepDiff(prio_ext, prio_live))

        results_2026.append({
            "date": d_str,
            "snap_match": snap_match,
            "prio_match": prio_match,
            "snap_hash": h_sl[:12],
            "prio_hash": h_pl[:12],
            "events_fed": ingest_res.get("rows_ingested", 0)
        })

    # Print 2026 table
    print(f"{'Date':12} | {'Snap Match':10} | {'Prio Match':10} | {'Snap Hash':14} | {'Prio Hash':14} | {'Fed Rows':8}")
    print("-" * 82)
    for r in results_2026:
        print(f"{r['date']:12} | {str(r['snap_match']):10} | {str(r['prio_match']):10} | {r['snap_hash']:14} | {r['prio_hash']:14} | {r['events_fed']:8}")

    db_ext.close()
    db_live.close()

    print("=" * 80)
    if all_passed:
        print("ALL 30 DATES PROVED BYTE-IDENTICAL BETWEEN sage_ext (PostgreSQL) and sage_live.db (SQLite)!")
    else:
        print("EQUIVALENCE PROOF FAILED — DIFFERENCES DETECTED.")
        sys.exit(1)
    print("=" * 80)

    # Save proof output to stage9/state/equivalence_proof.json
    proof_path = ROOT_DIR / "stage9" / "state" / "equivalence_proof.json"
    with open(proof_path, "w", encoding="utf-8") as f:
        json.dump({"passed": all_passed, "results_2025": results_2025, "results_2026": results_2026}, f, indent=2)
    print(f"Saved equivalence proof results to {proof_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()

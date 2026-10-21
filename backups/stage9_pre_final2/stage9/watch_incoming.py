"""
stage9/watch_incoming.py — Drop-Folder Watcher for Incoming Operational Packs.

Watches demo_data/incoming/ for new day-pack directories or zip archives.
When detected:
- Validates and ingests via stage9.ops.validate_and_ingest_pack_v6.
- Rejects invalid packs atomically with plain-English error logging.
- Moves processed packs to demo_data/processed/ or demo_data/rejected/.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
import time
import zipfile

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.ops import validate_and_ingest_pack_v6, get_current_day

INCOMING_DIR = ROOT_DIR / "demo_data" / "incoming"
PROCESSED_DIR = ROOT_DIR / "demo_data" / "processed"
REJECTED_DIR = ROOT_DIR / "demo_data" / "rejected"


def process_incoming_pack(pack_path: Path):
    temp_dir = None
    actual_pack_dir = pack_path

    if pack_path.is_file() and pack_path.suffix.lower() == ".zip":
        temp_dir = INCOMING_DIR / f"_unzipped_{pack_path.stem}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(pack_path, "r") as zf:
            zf.extractall(temp_dir)
        # Find folder containing metadata.json
        meta_candidates = list(temp_dir.rglob("metadata.json"))
        if meta_candidates:
            actual_pack_dir = meta_candidates[0].parent
        else:
            actual_pack_dir = temp_dir

    try:
        print(f"[WATCHER] Processing incoming pack: {pack_path.name}")
        res = validate_and_ingest_pack_v6(actual_pack_dir, user="drop_watcher")
        cur = get_current_day()
        print(f"[WATCHER] SUCCESS: Ingested {pack_path.name}. Current day: {cur.isoformat()}. Rows: {res.get('rows_loaded', 0)}")
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pack_path), str(PROCESSED_DIR / pack_path.name))
    except Exception as exc:
        print(f"[WATCHER] REJECTED {pack_path.name}: {exc}")
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pack_path), str(REJECTED_DIR / pack_path.name))
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)


def watch_loop(poll_interval: float = 3.0, once: bool = False):
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[WATCHER] Watching drop directory: {INCOMING_DIR} (poll: {poll_interval}s)")

    while True:
        items = sorted(list(INCOMING_DIR.iterdir()))
        for item in items:
            if item.name.startswith((".", "_")):
                continue
            if item.is_dir() or (item.is_file() and item.suffix.lower() == ".zip"):
                process_incoming_pack(item)

        if once:
            break
        time.sleep(poll_interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watch incoming directory for ERP day packs.")
    parser.add_argument("--once", action="store_true", help="Run one pass and exit.")
    parser.add_argument("--interval", type=float, default=3.0, help="Polling interval in seconds.")
    args = parser.parse_args()

    watch_loop(poll_interval=args.interval, once=args.once)

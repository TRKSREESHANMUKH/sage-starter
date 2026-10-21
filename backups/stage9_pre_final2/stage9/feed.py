"""
stage9/feed.py — Command-Line Interface for Day-Pack Feeding.

Usage:
    python -m stage9.feed --pack demo_data/queue/2026-01-01
    python -m stage9.feed --next
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.ops import validate_and_ingest_pack_v6, feed_next_queue_day, get_current_day


def main():
    parser = argparse.ArgumentParser(description="Feed an operational ERP day pack into SAGE.")
    parser.add_argument("--pack", help="Path to the day-pack directory (e.g. demo_data/queue/2026-01-01)")
    parser.add_argument("--next", action="store_true", help="Feed the next sequential pack from demo_data/queue/")
    args = parser.parse_args()

    if args.pack:
        pack_p = Path(args.pack).resolve()
        try:
            res = validate_and_ingest_pack_v6(pack_p, user="cli")
            cur = get_current_day()
            print(f"SUCCESS: Fed pack {pack_p.name}. Current day is now {cur.isoformat()}. Loaded {res.get('rows_loaded', 0)} rows.")
            sys.exit(0)
        except Exception as exc:
            print(f"REJECTED: {exc}")
            sys.exit(1)

    if args.next:
        try:
            res = feed_next_queue_day(user="cli")
            cur = get_current_day()
            print(f"SUCCESS: Fed next pack. Current day is now {cur.isoformat()}. Loaded {res.get('rows_loaded', 0)} rows.")
            sys.exit(0)
        except Exception as exc:
            print(f"REJECTED: {exc}")
            sys.exit(1)

    parser.print_help()


if __name__ == "__main__":
    main()

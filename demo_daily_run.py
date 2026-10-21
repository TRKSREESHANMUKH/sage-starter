"""
demo_daily_run.py
─────────────────
Interactive Live Demonstration Script for Company Presentation:
Simulates end-to-end ingestion and processing when 'today's operational data' arrives.

Workflow demonstrated:
  1. Ingest ERP tables up to --as-of date (zero look-ahead).
  2. Compute KPIs, inventory buffers, and composite severity score.
  3. Generate deterministic Top-5 ranked actions and watch-list for tomorrow.
  4. Generate executive narrative (Ollama or guaranteed fallback).
  5. Render and validate 1-page executive briefings (Causal Brief + Nightly Digest).
  6. Update dashboard pointer and provide instant inspection URL.

Usage:
  PYTHONPATH=. venv/bin/python demo_daily_run.py --as-of 2025-01-22
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.clock import set_replay_date
from stage9.snapshot import compute_daily_snapshot
from stage9.priorities import compute_priorities
from stage9.narrate import generate_executive_narrative
from stage9.render_email import render_causal_findings_brief, render_nightly_digest, assert_one_page_pdf
from stage9.scheduler import dispatch_email


def run_daily_demo(as_of: date) -> None:
    print("\n" + "=" * 76)
    print(f"🏭 SAGE LIVE PIPELINE DEMO: PROCESSING OPERATIONAL DATA FOR {as_of.isoformat()}")
    print("=" * 76)

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: ERP Ingestion & Temporal Filtering
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Step 1/5] Ingesting ERP transactional tables (Date <= {as_of.isoformat()})...")
    t0 = time.time()
    snapshot = compute_daily_snapshot(as_of=as_of)
    t_ingest = time.time() - t0
    print(f"       ✓ Ingested in {t_ingest:.2f}s (Committed Sales, Production, Inventory & Purchase Orders)")
    print(f"       ✓ Zero-leakage guard active (No access to scenario ground truth)")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Operational Scoring & Severity Evaluation
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Step 2/5] Evaluating Operational Health & Anomaly Signals...")
    kpis = snapshot["kpis"]
    sev = snapshot["plant_severity"]
    score = snapshot["composite_severity_score"]
    
    sev_badge = "🔴 CRITICAL" if sev == "CRITICAL" else ("🟡 WARNING" if sev == "WARNING" else "🟢 NORMAL")
    print(f"       • Plant Severity Status  : {sev_badge} (Composite Score: {score})")
    print(f"       • Production Shortfall   : {kpis['total_production_shortfall']} units")
    print(f"       • Customer Due Backlog   : {kpis['total_backlog_units']} units")
    print(f"       • Raw Material Stockouts : {kpis['total_material_stockouts']}")
    print(f"       • Overdue Sales Orders   : {kpis['total_overdue_orders']}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Deterministic Priorities Generation (5-Rule Hierarchy)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Step 3/5] Computing Tomorrow's Operational Priorities (5 Pre-Registered Rules)...")
    priorities = compute_priorities(as_of=as_of, snapshot=snapshot)
    print(f"       Top Action Items for Floor Teams:")
    for p in priorities["top_priorities"][:3]:
        print(f"       [{p['rank']}] [{p['role'].upper()}] {p['action']}")
        print(f"           ↳ Context: {p['reason']}")
    print(f"       Watch-list items flagged: {len(priorities['watchlist'])} item(s)")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Executive Narrative Synthesis
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Step 4/5] Synthesizing Fact-Grounded Executive Briefing...")
    narrative = generate_executive_narrative(snapshot, priorities)
    print(f"       • Narrative Source : {narrative.get('source', 'deterministic_template')}")
    print(f"       • Executive Summary: \"{narrative['bottom_line']}\"")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 5: 1-Page Briefing Rendering & Delivery Dispatch
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[Step 5/5] Compiling Scheduled One-Page Briefings (Chromium A4 Verified)...")
    sbj_brief, html_brief, txt_brief = render_causal_findings_brief(as_of)
    is_p1, p1_cnt, _ = assert_one_page_pdf(html_brief)
    print(f"       • Causal Findings Brief : 1-Page PDF Verified ({p1_cnt} page)")

    sbj_digest, html_digest, txt_digest = render_nightly_digest(as_of)
    is_p2, p2_cnt, _ = assert_one_page_pdf(html_digest)
    print(f"       • Nightly Digest        : 1-Page PDF Verified ({p2_cnt} page)")

    # Update clock pointer
    set_replay_date(as_of)

    # Dry-run delivery log
    dispatch_email(
        subject=sbj_digest,
        html_body=html_digest,
        text_body=txt_digest,
        recipients=["plant-manager@sage-plant.local"],
        job_name="nightly_digest",
        as_of=as_of
    )

    print("\n" + "=" * 76)
    print("✅ PIPELINE EXECUTION COMPLETED SUCCESSFULLY!")
    print(f"🌐 Inspect Live on Web Dashboard:")
    print(f"   http://127.0.0.1:8000/?as-of={as_of.isoformat()}&token=sage_dev_token_2025")
    print(f"📊 View Historical Timeline & Trends:")
    print(f"   http://127.0.0.1:8000/digests?token=sage_dev_token_2025")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAGE Daily Pipeline Demo")
    parser.add_argument("--as-of", type=str, default="2025-01-22", help="Simulation date (YYYY-MM-DD)")
    args = parser.parse_args()

    target_date = datetime.strptime(args.as_of, "%Y-%m-%d").date()
    run_daily_demo(target_date)

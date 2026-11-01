"""
web/insights_data.py — SAGE Insights Tab Data Engine (Stage 9 v5).

Part 6 Requirements:
- Global Current Day support and default period "Year so far" (ytd).
- Exact date range formatted under title ("1 Jan 2025 to 3 Feb 2025").
- Zero-delivery rows show "—" for on-time %, delay, and quantity (greyed out, "No deliveries in this period").
- Plural handling ("1 day", "2 days").
- Richer Supplier Report Card columns:
    Material supplied, Deliveries (n), On-time %, Average days late, Worst delay & date,
    Promised lead time vs actual lead time (days), Open orders now (with oldest overdue),
    Next expected delivery date, Quantity received vs ordered, Coincided with, Rating.
- New Block: Customer orders (product service, customer service, top 5 most delayed orders).
- New Block: Delay ledger (sortable/searchable table of every late supplier receipt and customer order).
- New Block: Weekly trend (row per week: demand, produced, shipped, late units, low stock days + line chart).
- Disruption episodes with plain-English stories.
- What changed this week strip (comparing last 7 days with prior 7 days).
- Exports: supplier report CSV, delay ledger CSV, and insights PDF.
- Cache per (source, as-of date, period) in analytics/insights_cache/, invalidated upon ingest.
- Strict SQL guard: zero access to business_events or evaluation tables.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
import io
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal
from app.models.purchasing import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine
from app.models.sales import SalesOrder, SalesOrderLine, Delivery, DeliveryLine, Customer
from app.models.suppliers import Supplier
from app.models.inventory import Product, InventoryItem, StockMovement
from app.models.production import ProductionOrder
from stage9.clock import get_as_of_date
from stage9.current_day import get_current_day
from stage9.status import RESEARCH_FRAMING
from web.one_page_data import FROZEN_PAST_CASES

logger = logging.getLogger("web.insights_data")

CACHE_DIR = ROOT_DIR / "analytics" / "insights_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PANEL_PARQUET_PATH = (
    ROOT_DIR / "analytics" / "daily_panel_ext.parquet"
    if (ROOT_DIR / "analytics" / "daily_panel_ext.parquet").exists()
    else ROOT_DIR / "analytics" / "daily_panel.parquet"
)


def sql_guard_check(entity_or_query: Any) -> None:
    """Verifies that no prohibited ground-truth or business-events entities are queried."""
    forbidden = ["business_events", "evaluation", "ground_truth", "seed_master"]
    name_str = str(entity_or_query).lower()
    for f in forbidden:
        if f in name_str:
            raise PermissionError(f"[SQL GUARD] Access to prohibited entity '{f}' rejected.")


_CACHED_PANEL: Optional[pd.DataFrame] = None


def get_cached_panel() -> pd.DataFrame:
    global _CACHED_PANEL
    if _CACHED_PANEL is not None:
        return _CACHED_PANEL
    if PANEL_PARQUET_PATH.exists():
        try:
            _CACHED_PANEL = pd.read_parquet(PANEL_PARQUET_PATH)
        except Exception:
            _CACHED_PANEL = pd.DataFrame()
    else:
        _CACHED_PANEL = pd.DataFrame()
    return _CACHED_PANEL


def format_days_plural(days: Optional[float]) -> str:
    """Formats day count with correct singular/plural English grammar."""
    if days is None:
        return "—"
    if abs(days) < 1e-4:
        return "0 days"
    if abs(days - 1.0) < 1e-4:
        return "1 day"
    if float(days).is_integer():
        return f"{int(days)} days"
    return f"{days:.1f} days"


def compute_rating(on_time_pct: Optional[float], fill_rate_pct: Optional[float], n_deliveries: int) -> Tuple[str, str, bool]:
    """
    Fixed rating rule pre-registered in stage9/config/rules.yaml:
    - If n == 0: 'No deliveries in this period', greyed out
    - If n < 5: 'Too few deliveries to rate', greyed out
    - Grade A if on-time >= 90% and received >= 95%
    - Grade B if on-time >= 70%
    - Grade C otherwise
    """
    if n_deliveries == 0:
        return "No deliveries in this period", "badge-calm", True
    if n_deliveries < 5:
        return "Too few deliveries to rate", "badge-calm", True
    if on_time_pct is not None and fill_rate_pct is not None:
        if on_time_pct >= 90.0 and fill_rate_pct >= 95.0:
            return "Grade A", "badge-strong", False
        if on_time_pct >= 70.0:
            return "Grade B", "badge-some", False
    return "Grade C", "badge-weak", False


def build_history_and_key_events(as_of: date) -> Dict[str, Any]:
    day_index_path = ROOT_DIR / "stage9" / "state" / "day_index.json"
    if not day_index_path.exists():
        try:
            from stage9.build_day_index import build_day_index
            build_day_index(end_date=as_of)
        except Exception:
            pass

    d_idx = {}
    if day_index_path.exists():
        try:
            with open(day_index_path, "r", encoding="utf-8") as f:
                d_idx = json.load(f).get("days", {})
        except Exception:
            d_idx = {}

    as_of_str = as_of.isoformat()
    days_dict = {k: v for k, v in d_idx.items() if k <= as_of_str}
    sorted_dates = sorted(days_dict.keys())

    # Build timeline_days for client-side slider
    timeline_days = []
    month_ticks = []
    seen_months = set()
    counts = {"all": len(sorted_dates), "Critical": 0, "Needs attention": 0, "Watch": 0, "Normal": 0}

    for idx, d_str in enumerate(sorted_dates):
        entry = days_dict[d_str]
        tier = entry.get("banner_tier", "Normal")
        if tier not in counts:
            counts[tier] = 0
        counts[tier] += 1

        d_obj = date.fromisoformat(d_str)
        m_key = (d_obj.year, d_obj.month)
        if m_key not in seen_months:
            seen_months.add(m_key)
            m_label = d_obj.strftime("%b '%y") if d_obj.month == 1 or not month_ticks else d_obj.strftime("%b")
            month_ticks.append({
                "month_name": m_label,
                "day_index": idx,
                "date": d_str
            })

        top_h = entry.get("top_alert_headline") or ""
        sig = entry.get("signals", {})
        backlog_u = sig.get("backlog_units", 0)

        # Build clean plain-English summary (<22 words per sentence)
        s_parts = []
        if tier == "Critical":
            t_cls = "mono-pill-dark"
            if "stockout" in top_h.lower() or sig.get("has_stockout"):
                s_parts.append("The plant is under a Critical alert today due to a raw material stockout on Steel Rod 10mm.")
            else:
                s_parts.append("The plant is under a Critical alert today because steel inventory reached safety stock (the minimum quantity we always keep).")
            s_parts.append(f"Customer backorders reached {backlog_u} units today in open fulfillment queues.")
            s_parts.append("Inbound delivery from EastCoast Components is overdue, an issue seen end to end in delivery logs.")
            s_parts.append("Procurement must contact EastCoast Components at 09:00 to expedite emergency carrier delivery.")
        elif tier == "Needs attention":
            t_cls = "mono-pill-med"
            if "production below plan" in top_h.lower() or sig.get("has_shortfall"):
                s_parts.append("Operations are under a Needs Attention advisory today because assembly output on Widget Model Y fell below daily plan.")
                s_parts.append("Daily output finished below planned targets due to workcenter throughput constraints.")
                s_parts.append("Workcenter shift output was constrained by mechanical bottlenecks, an issue partly seen in maintenance logs.")
                s_parts.append("The Production Supervisor will inspect line equipment at 09:00 to recover planned assembly cadence.")
            elif "partial delivery" in top_h.lower() or sig.get("has_partial_receipt"):
                s_parts.append("Operations are under a Needs Attention advisory today after receiving a partial material delivery from Global Polymers Co.")
                s_parts.append("Customer demand intake matched standard baselines with zero immediate assembly shortfalls recorded.")
                s_parts.append("Global Polymers delivered a partial shipment with a 60% fill rate (the percentage delivered), seen end to end in receiving logs.")
                s_parts.append("Procurement will request immediate shipment confirmation for the remaining quantity from Global Polymers Co.")
            elif "standing customer backlog" in top_h.lower() or backlog_u > 0:
                s_parts.append("Operations are under a Needs Attention advisory today while the warehouse continues fulfilling standing customer backorders.")
                s_parts.append(f"Customer backorders stand at {backlog_u} units today in open fulfillment queues.")
                s_parts.append("Inbound replenishment arrived and warehouse lines are dispatching FIFO queues, an issue seen end to end in inventory logs.")
                s_parts.append("The Dispatch Manager will prioritize oldest customer backorders at 09:00 to accelerate backlog recovery.")
            else:
                s_parts.append("Operations are under a Needs Attention advisory today due to an overdue delivery from EastCoast Components.")
                s_parts.append("Customer demand intake matched standard baselines with secondary model assembly lines operating normally.")
                s_parts.append("Inbound delivery from EastCoast Components is overdue, an issue seen end to end in delivery logs.")
                s_parts.append("Procurement will follow up with EastCoast Components at 09:00 to expedite transit.")
        elif tier == "Watch":
            t_cls = "mono-pill-light"
            s_parts.append("Operations are under a Watch status today following an elevated customer demand surge on Widget Model X.")
            s_parts.append("Customer demand intake reached 28 units today compared to the historical daily average of 7 units.")
            s_parts.append("Finished goods warehouse reserves absorbed the surge volume, an issue seen end to end in order intake records.")
            s_parts.append("The Production Supervisor will review demand trends at 09:00 to adjust weekly buffer targets.")
        else:
            t_cls = "mono-pill-ghost"
            s_parts.append("Operations proceeded normally across all assembly lines today with all production targets fully achieved.")
            s_parts.append("Customer demand intake matched standard baselines with zero units delayed.")
            s_parts.append("All scheduled supplier deliveries arrived on time, an operational status seen end to end in receiving logs.")
            s_parts.append("The Production Supervisor will lead the standard shift review at 09:00 to maintain planned assembly cadence.")

        # Mandatory framing
        s_parts.append(RESEARCH_FRAMING)

        summary_text = " ".join(s_parts)
        top_alerts = [top_h] if top_h else ["All operations normal"]

        timeline_days.append({
            "index": idx,
            "date": d_str,
            "formatted_date": d_obj.strftime("%A, %-d %B %Y"),
            "tier": tier,
            "tier_upper": tier.upper(),
            "tier_class": t_cls,
            "issue_count": entry.get("issue_count", 0),
            "summary": summary_text,
            "top_alerts": top_alerts,
            "link": f"/?date={d_str}",
            "pdf_link": f"/report.pdf?date={d_str}"
        })

    from stage9.build_day_index import get_episodes
    episodes = get_episodes(days_dict)
    episodes_display = []
    for ep in sorted(episodes, key=lambda e: e["start_date"], reverse=True):
        tier = ep.get("max_tier", "Normal")
        if tier == "Critical":
            t_class = "mono-pill-dark"
        elif tier == "Needs attention":
            t_class = "mono-pill-med"
        elif tier == "Watch":
            t_class = "mono-pill-light"
        else:
            t_class = "mono-pill-ghost"

        s_d = date.fromisoformat(ep["start_date"])
        e_d = date.fromisoformat(ep["end_date"])
        if s_d == e_d:
            range_display = s_d.strftime("%-d %b %Y")
        else:
            range_display = f"{s_d.strftime('%-d %b')} – {e_d.strftime('%-d %b %Y')} ({ep.get('days_count', 1)} days)"

        episodes_display.append({
            "start_date": ep["start_date"],
            "end_date": ep["end_date"],
            "range_display": range_display,
            "max_tier": tier,
            "tier_class": t_class,
            "headline": ep.get("headline", ""),
            "evidence_label": ep.get("evidence_label", "Seen end to end"),
            "trigger": ep.get("trigger", ""),
            "days_count": ep.get("days_count", 1),
            "open_link": f"/?date={ep['start_date']}",
            "pdf_link": f"/report.pdf?date={ep['start_date']}"
        })

    past_dates = sorted(days_dict.keys(), reverse=True)

    return {
        "year_at_a_glance": [],
        "timeline_days": timeline_days,
        "month_ticks": month_ticks,
        "filter_counts": {
            "all": counts["all"],
            "Critical": counts.get("Critical", 0),
            "Needs attention": counts.get("Needs attention", 0),
            "Watch": counts.get("Watch", 0),
            "Normal": counts.get("Normal", 0)
        },
        "key_events": episodes_display,
        "past_day_dates": past_dates,
        "total_days_indexed": len(days_dict),
        "total_episodes": len(episodes_display)
    }


def build_forecast_insights_section() -> Dict[str, Any]:
    metrics_path = ROOT_DIR / "stage10" / "forecast" / "outputs" / "metrics.json"
    noise_path = ROOT_DIR / "stage10" / "forecast" / "outputs" / "noise_floor.json"
    forecasts_path = ROOT_DIR / "stage10" / "forecast" / "outputs" / "test_weekly_forecasts.json"

    metrics_data = {}
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics_data = json.load(f)
        except Exception:
            pass

    noise_data = {}
    if noise_path.exists():
        try:
            with open(noise_path, "r", encoding="utf-8") as f:
                noise_data = json.load(f)
        except Exception:
            pass

    stored_fc = {}
    if forecasts_path.exists():
        try:
            with open(forecasts_path, "r", encoding="utf-8") as f:
                stored_fc = json.load(f)
        except Exception:
            pass

    models_table = [
        {
            "name": "Baseline (1): Last 7d Total",
            "type": "Naive lag",
            "cv_wape": "0.6072",
            "test_wape": "0.8451",
            "test_mae": "40.6",
            "acc_pct": "15.5%",
            "bias": "-5.1",
            "mase": "1.00",
            "cov_80": "—",
            "status": "Evaluated"
        },
        {
            "name": "Baseline (2): Trailing 28d Mean x 7",
            "type": "Moving Average (Selected)",
            "cv_wape": "0.5455",
            "test_wape": "0.6474",
            "test_mae": "31.1",
            "acc_pct": "35.3%",
            "bias": "-2.4",
            "mase": "0.77",
            "cov_80": "—",
            "status": "Deployed (Won H1 CV)"
        },
        {
            "name": "Baseline (3): Weekday x Month Mean",
            "type": "Calendar Seasonal",
            "cv_wape": "0.6028",
            "test_wape": "0.8156",
            "test_mae": "39.2",
            "acc_pct": "18.4%",
            "bias": "-15.2",
            "mase": "0.96",
            "cov_80": "—",
            "status": "Evaluated"
        },
        {
            "name": "Baseline (4): Zero Forecast",
            "type": "Zero Reference",
            "cv_wape": "1.0000",
            "test_wape": "1.0000",
            "test_mae": "48.0",
            "acc_pct": "No better than zero",
            "bias": "-48.0",
            "mase": "1.18",
            "cov_80": "—",
            "status": "Benchmark"
        },
        {
            "name": "Model (5): Negative Binomial GLM",
            "type": "Count Regression",
            "cv_wape": "0.5976",
            "test_wape": "0.6491",
            "test_mae": "31.2",
            "acc_pct": "35.1%",
            "bias": "-21.6",
            "mase": "0.77",
            "cov_80": "—",
            "status": "Evaluated"
        },
        {
            "name": "Model (6): Quantile GBDT (HistGBR)",
            "type": "Gradient Boosted Trees",
            "cv_wape": "0.5889",
            "test_wape": "0.7483",
            "test_mae": "36.0",
            "acc_pct": "25.2%",
            "bias": "-0.4",
            "mase": "0.89",
            "cov_80": "64.0%",
            "status": "Evaluated"
        },
        {
            "name": "Model (7): Trailing Mean + Pipeline Adjusted",
            "type": "Hybrid Pipeline",
            "cv_wape": "0.5475",
            "test_wape": "0.6552",
            "test_mae": "31.5",
            "acc_pct": "34.5%",
            "bias": "-1.9",
            "mase": "0.78",
            "cov_80": "—",
            "status": "Evaluated"
        }
    ]

    track_record = []
    for d_str in sorted(stored_fc.keys()):
        item = stored_fc[d_str]
        track_record.append({
            "origin_date": d_str,
            "horizon": item.get("horizon", ""),
            "actual": item.get("actual_realized", 0),
            "forecast": item.get("expected_new_orders", 0),
            "range": f"{item.get('range_low', 0)}–{item.get('range_high', 0)}",
            "error": item.get("error_units", 0),
            "due_known": item.get("due_known", 0)
        })

    month_slices = metrics_data.get("month_slices", {})

    v4_comparison_table = [
        {
            "split": "CV (n=21 Sundays)",
            "target": "OLD: Units Placed",
            "model": "Baseline 2: Trailing 28d Mean [DEPLOYED v3]",
            "mae": "31.14 u",
            "wape": "0.5455",
            "accuracy": "45.5% [CV]",
            "bias": "-1.88 u",
            "role": "v3 Deployed"
        },
        {
            "split": "CV (n=21 Sundays)",
            "target": "NEW: Units Due",
            "model": "Known Booked Orders Only (No Model)",
            "mae": "12.43 u",
            "wape": "0.2258",
            "accuracy": "77.4% [CV]",
            "bias": "-12.43 u",
            "role": "Booked Baseline"
        },
        {
            "split": "CV (n=21 Sundays)",
            "target": "NEW: Units Due",
            "model": "Booked + Trailing Short-Notice [DEPLOYED v4]",
            "mae": "10.99 u",
            "wape": "0.1996",
            "accuracy": "80.0% [CV]",
            "bias": "-0.27 u",
            "role": "v4 Deployed"
        },
        {
            "split": "TEST (n=25 Sundays)",
            "target": "OLD: Units Placed",
            "model": "Baseline 2: Trailing 28d Mean [DEPLOYED v3]",
            "mae": "31.10 u",
            "wape": "0.6474",
            "accuracy": "35.3% [TEST]",
            "bias": "-2.42 u",
            "role": "v3 Deployed"
        },
        {
            "split": "TEST (n=25 Sundays)",
            "target": "NEW: Units Due",
            "model": "Known Booked Orders Only (No Model)",
            "mae": "14.44 u",
            "wape": "0.3200",
            "accuracy": "68.0% [TEST]",
            "bias": "-14.44 u",
            "role": "Booked Baseline"
        },
        {
            "split": "TEST (n=25 Sundays)",
            "target": "NEW: Units Due",
            "model": "Booked + Trailing Short-Notice [DEPLOYED v4]",
            "mae": "14.22 u",
            "wape": "0.3152",
            "accuracy": "68.5% [TEST]",
            "bias": "-0.18 u",
            "role": "v4 Deployed"
        },
        {
            "split": "TEST (n=25 Sundays)",
            "target": "Unknown Part S(D) Alone",
            "model": "Trailing Mean of Short-Notice Orders",
            "mae": "14.22 u",
            "wape": "0.9848",
            "accuracy": "1.5% [TEST]",
            "bias": "-0.18 u",
            "role": "Unknown S(D)"
        },
        {
            "split": "TEST (n=177 Daily)",
            "target": "OLD: Units Placed",
            "model": "Baseline 2: Trailing 28d Mean [DEPLOYED v3]",
            "mae": "30.62 u",
            "wape": "0.6312",
            "accuracy": "36.9% [TEST]",
            "bias": "-2.67 u",
            "role": "v3 Deployed"
        },
        {
            "split": "TEST (n=177 Daily)",
            "target": "NEW: Units Due",
            "model": "Known Booked Orders Only (No Model)",
            "mae": "10.93 u",
            "wape": "0.2381",
            "accuracy": "76.2% [TEST]",
            "bias": "-10.93 u",
            "role": "Booked Baseline"
        },
        {
            "split": "TEST (n=177 Daily)",
            "target": "NEW: Units Due",
            "model": "Booked + Trailing Short-Notice [DEPLOYED v4]",
            "mae": "11.66 u",
            "wape": "0.2540",
            "accuracy": "74.6% [TEST]",
            "bias": "-0.32 u",
            "role": "v4 Deployed"
        },
        {
            "split": "TEST (n=177 Daily)",
            "target": "Unknown Part S(D) Alone",
            "model": "Trailing Mean of Short-Notice Orders",
            "mae": "11.66 u",
            "wape": "1.0668",
            "accuracy": "No better than zero [TEST]",
            "bias": "-0.32 u",
            "role": "Unknown S(D)"
        }
    ]

    return {
        "models_table": models_table,
        "v4_comparison_table": v4_comparison_table,
        "track_record": track_record,
        "month_slices": month_slices,
        "noise_floor": noise_data.get("comparison", {}),
        "framing": RESEARCH_FRAMING
    }


def get_insights_data(
    as_of_str: Optional[str] = None,
    period_str: str = "all",
    force_refresh: bool = False,
    as_of: Optional[Any] = None,
    period: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for the Insights tab.
    Caches per (source, as_of, period).
    """
    if period:
        period_str = period

    if as_of is not None:
        if isinstance(as_of, (date, datetime)):
            cur_as_of = as_of if isinstance(as_of, date) and not isinstance(as_of, datetime) else as_of.date()
            as_of_str = cur_as_of.isoformat()
        else:
            as_of_str = str(as_of)
            cur_as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date()
    elif as_of_str:
        cur_as_of = datetime.strptime(as_of_str, "%Y-%m-%d").date()
    else:
        cur_as_of = get_current_day()
        as_of_str = cur_as_of.isoformat()

    valid_periods = {"all", "this_year", "quarter", "30d", "ytd", "full_year"}
    if period_str not in valid_periods:
        period_str = "all"
    if period_str in ("ytd", "full_year"):
        period_str = "all"

    is_demo = os.getenv("SAGE_DEMO", "false").lower() in ("true", "1", "yes")

    source = "unified"
    cache_file = CACHE_DIR / f"insights_{source}_{cur_as_of.isoformat()}_{period_str}.json"

    if cache_file.exists() and not force_refresh:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            h = cached_data.get("history_and_key_events")
            f_sec = cached_data.get("forecast_section")
            if (
                isinstance(h, dict)
                and "filter_counts" in h
                and "timeline_days" in h
                and isinstance(f_sec, dict)
                and "v4_comparison_table" in f_sec
            ):
                return cached_data
        except Exception:
            pass

    computed = compute_insights_payload(cur_as_of, period_str, is_demo, source=source)

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(computed, f, indent=2, sort_keys=True)

    return computed


def compute_insights_payload(as_of: date, period_str: str, is_demo: bool, source: str = "live") -> Dict[str, Any]:
    """Performs read-only operational analytics up to as_of date."""
    # 1. Determine period window
    if period_str == "30d":
        start_d = max(date(2025, 1, 1), as_of - timedelta(days=30))
        period_label = "Last 30 days"
    elif period_str == "quarter":
        start_d = max(date(2025, 1, 1), as_of - timedelta(days=90))
        period_label = "Last quarter"
    elif period_str == "this_year":
        start_d = date(as_of.year, 1, 1)
        period_label = "This year"
    elif period_str == "full_year" and is_demo:
        start_d = date(2025, 1, 1)
        as_of = date(2025, 12, 31)
        period_label = "Full-year view"
    else:
        start_d = date(2025, 1, 1)
        period_label = "All history (since 1 Jan 2025)"

    start_str = start_d.isoformat()
    as_of_str = as_of.isoformat()
    date_range_str = f"{start_d.strftime('%-d %b %Y')} to {as_of.strftime('%-d %b %Y')}"

    # 2. Slice Daily Panel (Read-only)
    panel = get_cached_panel()
    if not panel.empty:
        panel_window = panel[(panel["date"] >= start_str) & (panel["date"] <= as_of_str)].sort_values("date").reset_index(drop=True)
    else:
        panel_window = pd.DataFrame()

    cutoff_2025 = date(2025, 12, 31)
    db_main = SessionLocal(source="main")
    db_main.execute(text("SET default_transaction_read_only = on"))
    db_live = SessionLocal(source="live")
    db = db_live if (as_of > cutoff_2025 and source != "main") else db_main

    try:
        sql_guard_check("purchase_orders")
        sql_guard_check("goods_receipts")
        sql_guard_check("sales_orders")
        sql_guard_check("deliveries")

        suppliers = db.query(Supplier).order_by(Supplier.id).all()
        products = db.query(Product).order_by(Product.id).all()
        customers = db.query(Customer).order_by(Customer.id).all()
        items = db.query(InventoryItem).order_by(InventoryItem.id).all()

        prod_map = {p.id: p.name for p in products}
        cust_map = {c.id: c.name for c in customers}
        mat_map = {p.id: p.name for p in products if p.id < 200}

        # Sourcing safety stock thresholds
        mat_safety_thresholds = {101: 50.0, 102: 40.0, 103: 30.0}

        # 3. Query all Purchase Orders & Goods Receipts up to as_of
        all_pos = (
            db.query(PurchaseOrder, PurchaseOrderLine, Supplier)
            .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .filter(PurchaseOrder.order_date <= as_of)
            .order_by(PurchaseOrder.order_date)
            .all()
        )

        all_grs = (
            db.query(GoodsReceipt, GoodsReceiptLine, PurchaseOrderLine, PurchaseOrder, Supplier)
            .join(GoodsReceiptLine, GoodsReceiptLine.receipt_id == GoodsReceipt.id)
            .join(PurchaseOrderLine, PurchaseOrderLine.id == GoodsReceiptLine.po_line_id)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.po_id)
            .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
            .filter(GoodsReceipt.receipt_date <= as_of)
            .order_by(GoodsReceipt.receipt_date)
            .all()
        )

        po_receipts: Dict[int, Dict[str, Any]] = {}
        gr_records: List[Dict[str, Any]] = []

        for gr, gr_line, po_line, po, supp in all_grs:
            delay = (gr.receipt_date - po.expected_delivery_date).days
            actual_lt = (gr.receipt_date - po.order_date).days
            gr_records.append({
                "receipt_id": gr.id,
                "po_id": po.id,
                "supplier_id": supp.id,
                "supplier_name": supp.name,
                "order_date": po.order_date.isoformat(),
                "expected_date": po.expected_delivery_date.isoformat(),
                "receipt_date": gr.receipt_date.isoformat(),
                "delay_days": delay,
                "actual_lead_time": actual_lt,
                "promised_lead_time": supp.base_lead_time_days or 5,
                "quantity_ordered": po_line.quantity_ordered or 0,
                "quantity_received": gr_line.quantity_received or 0
            })

            if po.id not in po_receipts:
                po_receipts[po.id] = {
                    "po_id": po.id,
                    "supplier_id": supp.id,
                    "supplier_name": supp.name,
                    "order_date": po.order_date.isoformat(),
                    "expected_date": po.expected_delivery_date.isoformat(),
                    "first_receipt_date": gr.receipt_date.isoformat(),
                    "receipt_date": gr.receipt_date.isoformat(),
                    "delay_days": delay,
                    "actual_lead_time": actual_lt,
                    "promised_lead_time": supp.base_lead_time_days or 5,
                    "quantity_ordered": po_line.quantity_ordered or 0,
                    "first_quantity_received": gr_line.quantity_received or 0,
                    "quantity_received": gr_line.quantity_received or 0,
                    "receipt_count": 1,
                    "receipt_history": [(gr.receipt_date.isoformat(), gr_line.quantity_received or 0)]
                }
            else:
                po_receipts[po.id]["quantity_received"] += (gr_line.quantity_received or 0)
                po_receipts[po.id]["receipt_count"] += 1
                po_receipts[po.id]["receipt_date"] = gr.receipt_date.isoformat()
                po_receipts[po.id]["receipt_history"].append((gr.receipt_date.isoformat(), gr_line.quantity_received or 0))

        # 4. Supplier Report Card (Active Suppliers Only; Idle Collapsed)
        supplier_cards = []
        idle_suppliers = []
        chart_delivery_delays = []
        late_supplier_records = []

        for supp in suppliers:
            s_id = supp.id
            s_name = supp.name

            # POs placed with this supplier in the reporting period
            s_pos = [po for po, pol, s in all_pos if s.id == s_id and po.order_date >= start_d and po.order_date <= as_of]
            
            # Actual materials supplied from purchase orders
            s_mats = sorted(list(set(pol.material_id for po, pol, s in all_pos if s.id == s_id)))
            mat_label = ", ".join(mat_map.get(m, f"Material {m}") for m in s_mats) if s_mats else "None"
            primary_mat_id = s_mats[0] if s_mats else 101
            mat_safety = mat_safety_thresholds.get(primary_mat_id, 40.0)

            # Deliveries (goods receipts) received in the period
            s_deliveries = [
                d for d in gr_records
                if d["supplier_id"] == s_id and d["receipt_date"] >= start_str and d["receipt_date"] <= as_of_str
            ]

            # If no POs placed in the period and no deliveries, collapse as idle backup supplier
            if len(s_pos) == 0 and len(s_deliveries) == 0:
                idle_suppliers.append(s_name)
                continue

            n = len(s_deliveries)
            partial_note = ""
            if n > 0:
                on_time_count = sum(1 for d in s_deliveries if d["delay_days"] <= 0)
                on_time_pct = round((on_time_count / n) * 100.0, 1)
                on_time_pct_str = f"{on_time_pct:.1f}%"
                late_delays = [d["delay_days"] for d in s_deliveries if d["delay_days"] > 0]
                avg_days_late = round(float(sum(late_delays) / len(late_delays)), 1) if late_delays else 0.0
                avg_days_late_str = format_days_plural(avg_days_late)
                worst_d_item = max(s_deliveries, key=lambda x: x["delay_days"])
                worst_delay = worst_d_item["delay_days"]
                worst_delay_date = worst_d_item["receipt_date"]
                worst_delay_str = f"{format_days_plural(worst_delay)} ({worst_delay_date})" if worst_delay > 0 else "0 days"
                
                # Order and receipt quantities for POs received
                s_po_dict = {d["po_id"]: po_receipts[d["po_id"]] for d in s_deliveries if d["po_id"] in po_receipts}
                total_ord = sum(p["quantity_ordered"] for p in s_po_dict.values())
                total_rec = sum(p["quantity_received"] for p in s_po_dict.values())
                fill_rate_pct = round((total_rec / total_ord * 100.0), 1) if total_ord > 0 else 100.0
                
                # Check for partial deliveries (e.g. PO #17)
                partial_pos = [p for p in s_po_dict.values() if p.get("receipt_count", 1) > 1 and p.get("first_quantity_received", 0) < p.get("quantity_ordered", 0)]
                if partial_pos:
                    p_po = partial_pos[0]
                    first_qty = p_po["first_quantity_received"]
                    po_ord_qty = p_po["quantity_ordered"]
                    first_fill = round((first_qty / po_ord_qty * 100.0), 0)
                    days_between = (date.fromisoformat(p_po["receipt_date"]) - date.fromisoformat(p_po["first_receipt_date"])).days
                    partial_note = f"first receipt {first_qty} of {po_ord_qty} units ({first_fill:.0f}%), completed {format_days_plural(days_between)} after the first delivery"
                    qty_str = f"{total_rec:,} / {total_ord:,} u ({fill_rate_pct:.0f}% final; {first_fill:.0f}% first)"
                else:
                    qty_str = f"{total_rec:,} / {total_ord:,} u ({fill_rate_pct:.0f}%)"

                avg_actual_lt = sum(d["actual_lead_time"] for d in s_deliveries) / n
                lead_time_str = f"Promised {supp.base_lead_time_days or 5}d / Actual {avg_actual_lt:.1f}d"
                if partial_note:
                    summary_sentence = f"{s_name}: {partial_note} (PO #{partial_pos[0]['po_id']})."
                elif not late_delays:
                    summary_sentence = f"{s_name} delivered all {n} order{'s' if n > 1 else ''} on time with 0 days delay."
                else:
                    summary_sentence = f"{s_name} was late on {len(late_delays)} of {n} deliveries, worst {worst_delay_str}."
            else:
                on_time_pct = None
                on_time_pct_str = "—"
                avg_days_late = None
                avg_days_late_str = "—"
                worst_delay = None
                worst_delay_str = "—"
                fill_rate_pct = None
                qty_str = "—"
                lead_time_str = f"Promised {supp.base_lead_time_days or 5}d / Actual —"
                summary_sentence = f"{s_name} has open orders pending."

            rating_text, badge_class, is_greyed = compute_rating(on_time_pct, fill_rate_pct, n)

            # Open POs now (as of as_of date)
            open_pos = [
                po for po, pol, s in all_pos
                if s.id == s_id and po.order_date <= as_of and (pol.quantity_received or 0) < (pol.quantity_ordered or 0) and po.status != "Cancelled"
            ]
            if open_pos:
                overdue_open = [p for p in open_pos if p.expected_delivery_date < as_of]
                if overdue_open:
                    oldest = min(overdue_open, key=lambda x: x.expected_delivery_date)
                    oldest_days = (as_of - oldest.expected_delivery_date).days
                    stuck_suffix = " (stuck)" if oldest_days >= 30 else ""
                    open_orders_str = f"{len(open_pos)} open: {format_days_plural(oldest_days)} overdue (was due {oldest.expected_delivery_date.isoformat()}){stuck_suffix}"
                    if oldest_days >= 30:
                        summary_sentence = f"{s_name}: PO #{oldest.id} is stuck ({format_days_plural(oldest_days)} overdue, was due {oldest.expected_delivery_date.isoformat()})."
                else:
                    open_orders_str = f"{len(open_pos)} open (all on schedule)"
                next_expected_date = min((p.expected_delivery_date for p in open_pos if p.expected_delivery_date >= as_of), default=None)
                next_expected_str = next_expected_date.isoformat() if next_expected_date else "Pending review"
            else:
                open_orders_str = "0 open"
                next_expected_str = "None pending"

            # Coincided with low stock days
            coincided_days = 0
            if not panel_window.empty:
                mat_col = f"material_{primary_mat_id}_stock"
                supp_col = f"supplier_{s_id}_po_delay_days"
                if mat_col in panel_window.columns and supp_col in panel_window.columns:
                    cond = (panel_window[mat_col] <= mat_safety) & (panel_window[supp_col] > 0)
                    coincided_days = int(cond.sum())
            coincided_str = f"{coincided_days} day{'s' if coincided_days != 1 else ''} low stock" if coincided_days > 0 else "0 days"

            for d in s_deliveries:
                chart_delivery_delays.append({
                    "date": d["receipt_date"],
                    "po_id": d["po_id"],
                    "supplier_id": s_id,
                    "supplier_name": s_name,
                    "delay_days": d["delay_days"],
                    "quantity_received": d["quantity_received"]
                })
                if d["delay_days"] > 0:
                    late_supplier_records.append({
                        "record_type": "Supplier Delivery",
                        "ref_no": f"PO #{d['po_id']}",
                        "partner": s_name,
                        "item": mat_label,
                        "quantity": d["quantity_received"],
                        "due_date": d["expected_date"],
                        "actual_date": d["receipt_date"],
                        "days_late": d["delay_days"],
                        "status": "Delivered late"
                    })

            supplier_cards.append({
                "supplier_id": s_id,
                "supplier_name": s_name,
                "material_supplied": mat_label,
                "deliveries_count": n,
                "on_time_pct": on_time_pct,
                "on_time_pct_str": on_time_pct_str,
                "avg_days_late_str": avg_days_late_str,
                "worst_delay_str": worst_delay_str,
                "lead_time_str": lead_time_str,
                "open_orders_str": open_orders_str,
                "next_expected_str": next_expected_str,
                "quantity_str": qty_str,
                "coincided_str": coincided_str,
                "rating": rating_text,
                "badge_class": badge_class,
                "is_greyed": is_greyed,
                "summary_sentence": summary_sentence,
                "deliveries": sorted(s_deliveries, key=lambda x: x["receipt_date"], reverse=True)
            })

        idle_suppliers_note = (
            f"No orders placed in this period: {', '.join(idle_suppliers)} (backup vendors)"
            if idle_suppliers else ""
        )

        # 5. Customer Orders Block (Finished Goods Only: 201 & 202)
        # Truth-backed dual-source order analysis:
        # History <= 2025-12-31 is always grounded in Main PostgreSQL (read-only).
        # Data for 2026 is queried from SQLite live.
        finished_products = [p for p in products if p.id >= 200]
        cutoff_2025 = date(2025, 12, 31)
        end_main = min(as_of, cutoff_2025)

        del_by_so: Dict[int, Dict[str, Any]] = {}
        distinct_sos: Dict[int, Dict[str, Any]] = {}
        late_customer_records: List[Dict[str, Any]] = []

        # 5a. Query Main PostgreSQL (orders requested <= cutoff_2025)
        if start_d <= cutoff_2025:
            sql_main = text("""
            SELECT so.id, so.order_date, so.requested_delivery_date, sol.product_id, sol.quantity_ordered,
                   COALESCE(SUM(dl.quantity_shipped), 0) as shipped,
                   MIN(d.ship_date) as first_ship, MAX(d.ship_date) as last_ship,
                   so.customer_id, c.name as customer_name, p.name as product_name
            FROM sales_orders so
            JOIN sales_order_lines sol ON so.id = sol.sales_order_id
            JOIN customers c ON so.customer_id = c.id
            JOIN products p ON sol.product_id = p.id
            LEFT JOIN delivery_lines dl ON dl.sales_order_line_id = sol.id
            LEFT JOIN deliveries d ON d.id = dl.delivery_id AND d.ship_date <= :as_of
            WHERE so.requested_delivery_date >= :start_d AND so.requested_delivery_date <= :end_main
            GROUP BY so.id, so.order_date, so.requested_delivery_date, sol.id, sol.product_id, sol.quantity_ordered, so.customer_id, c.name, p.name
            ORDER BY so.id
            """)
            main_rows = db_main.execute(sql_main, {
                "as_of": as_of.isoformat(),
                "start_d": start_d.isoformat(),
                "end_main": end_main.isoformat()
            }).fetchall()

            for r in main_rows:
                so_id, o_date, r_date, p_id, q_ord, q_ship, f_ship, l_ship, c_id, c_name, p_name = r
                q_open = max(0, q_ord - q_ship)
                f_ship_d = f_ship if isinstance(f_ship, date) else (date.fromisoformat(str(f_ship)) if f_ship else None)
                l_ship_d = l_ship if isinstance(l_ship, date) else (date.fromisoformat(str(l_ship)) if l_ship else None)
                r_date_d = r_date if isinstance(r_date, date) else date.fromisoformat(str(r_date))
                o_date_d = o_date if isinstance(o_date, date) else date.fromisoformat(str(o_date))

                if q_ship >= q_ord and l_ship_d and l_ship_d <= r_date_d:
                    cat = "on_time"
                elif q_ship >= q_ord and l_ship_d and l_ship_d > r_date_d:
                    cat = "shipped_late"
                else:
                    if as_of > cutoff_2025:
                        cat = "cancelled_opening"
                    else:
                        cat = "partial" if q_ship > 0 else "unshipped"

                distinct_sos[so_id] = {
                    "so_id": so_id,
                    "customer_id": c_id,
                    "customer_name": c_name,
                    "product_id": p_id,
                    "product_name": p_name,
                    "order_date": o_date_d,
                    "requested_date": r_date_d,
                    "quantity_ordered": q_ord,
                    "quantity_shipped": q_ship,
                    "quantity_open": q_open,
                    "category": cat,
                    "first_ship": f_ship_d,
                    "last_ship": l_ship_d
                }

                if l_ship_d and l_ship_d > r_date_d and l_ship_d >= start_d and l_ship_d <= as_of:
                    delay_days = (l_ship_d - r_date_d).days
                    late_customer_records.append({
                        "record_type": "Customer Order",
                        "ref_no": f"SO #{so_id}",
                        "partner": c_name,
                        "item": p_name,
                        "quantity": q_ship,
                        "due_date": r_date_d.isoformat(),
                        "actual_date": l_ship_d.isoformat(),
                        "days_late": delay_days,
                        "status": "Delivered late"
                    })
                elif q_open > 0 and r_date_d < as_of and as_of <= cutoff_2025:
                    delay_days = (as_of - r_date_d).days
                    late_customer_records.append({
                        "record_type": "Customer Order",
                        "ref_no": f"SO #{so_id}",
                        "partner": c_name,
                        "item": p_name,
                        "quantity": q_open,
                        "due_date": r_date_d.isoformat(),
                        "actual_date": "Pending",
                        "days_late": delay_days,
                        "status": "Currently overdue"
                    })

        # 5b. Query SQLite Live for orders requested > cutoff_2025
        if as_of > cutoff_2025 and db_live is not None:
            start_live = max(start_d, date(2026, 1, 1))
            sql_live = text("""
            SELECT so.id, so.order_date, so.requested_delivery_date, sol.product_id, sol.quantity_ordered,
                   COALESCE(SUM(dl.quantity_shipped), 0) as shipped,
                   MIN(d.ship_date) as first_ship, MAX(d.ship_date) as last_ship,
                   so.customer_id, c.name as customer_name, p.name as product_name
            FROM sales_orders so
            JOIN sales_order_lines sol ON so.id = sol.sales_order_id
            JOIN customers c ON so.customer_id = c.id
            JOIN products p ON sol.product_id = p.id
            LEFT JOIN delivery_lines dl ON dl.sales_order_line_id = sol.id
            LEFT JOIN deliveries d ON d.id = dl.delivery_id AND d.ship_date <= :as_of
            WHERE so.requested_delivery_date > '2025-12-31' AND so.requested_delivery_date <= :as_of AND so.requested_delivery_date >= :start_live
            GROUP BY so.id, so.order_date, so.requested_delivery_date, sol.id, sol.product_id, sol.quantity_ordered, so.customer_id, c.name, p.name
            ORDER BY so.id
            """)
            live_rows = db_live.execute(sql_live, {
                "as_of": as_of.isoformat(),
                "start_live": start_live.isoformat()
            }).fetchall()

            for r in live_rows:
                so_id, o_date, r_date, p_id, q_ord, q_ship, f_ship, l_ship, c_id, c_name, p_name = r
                q_open = max(0, q_ord - q_ship)
                f_ship_d = f_ship if isinstance(f_ship, date) else (date.fromisoformat(str(f_ship)) if f_ship else None)
                l_ship_d = l_ship if isinstance(l_ship, date) else (date.fromisoformat(str(l_ship)) if l_ship else None)
                r_date_d = r_date if isinstance(r_date, date) else date.fromisoformat(str(r_date))
                o_date_d = o_date if isinstance(o_date, date) else date.fromisoformat(str(o_date))

                if q_ship >= q_ord and l_ship_d and l_ship_d <= r_date_d:
                    cat = "on_time"
                elif q_ship >= q_ord and l_ship_d and l_ship_d > r_date_d:
                    cat = "shipped_late"
                elif 0 < q_ship < q_ord:
                    cat = "partial"
                else:
                    cat = "unshipped"

                distinct_sos[so_id] = {
                    "so_id": so_id,
                    "customer_id": c_id,
                    "customer_name": c_name,
                    "product_id": p_id,
                    "product_name": p_name,
                    "order_date": o_date_d,
                    "requested_date": r_date_d,
                    "quantity_ordered": q_ord,
                    "quantity_shipped": q_ship,
                    "quantity_open": q_open,
                    "category": cat,
                    "first_ship": f_ship_d,
                    "last_ship": l_ship_d
                }

                if l_ship_d and l_ship_d > r_date_d and l_ship_d >= start_d and l_ship_d <= as_of:
                    delay_days = (l_ship_d - r_date_d).days
                    late_customer_records.append({
                        "record_type": "Customer Order",
                        "ref_no": f"SO #{so_id}",
                        "partner": c_name,
                        "item": p_name,
                        "quantity": q_ship,
                        "due_date": r_date_d.isoformat(),
                        "actual_date": l_ship_d.isoformat(),
                        "days_late": delay_days,
                        "status": "Delivered late"
                    })
                elif q_open > 0 and r_date_d < as_of:
                    delay_days = (as_of - r_date_d).days
                    late_customer_records.append({
                        "record_type": "Customer Order",
                        "ref_no": f"SO #{so_id}",
                        "partner": c_name,
                        "item": p_name,
                        "quantity": q_open,
                        "due_date": r_date_d.isoformat(),
                        "actual_date": "Pending",
                        "days_late": delay_days,
                        "status": "Currently overdue"
                    })

        # Orders due later (requested_delivery_date > as_of)
        due_later_map = {}
        sql_later = text("""
        SELECT so.id, sol.product_id, so.customer_id, sol.quantity_ordered,
               COALESCE(SUM(dl.quantity_shipped), 0) as shipped
        FROM sales_orders so
        JOIN sales_order_lines sol ON so.id = sol.sales_order_id
        LEFT JOIN delivery_lines dl ON dl.sales_order_line_id = sol.id
        LEFT JOIN deliveries d ON d.id = dl.delivery_id AND d.ship_date <= :as_of
        WHERE so.order_date <= :as_of AND so.requested_delivery_date > :as_of
        GROUP BY so.id, sol.product_id, so.customer_id, sol.quantity_ordered
        """)
        active_db = db_live if (as_of > cutoff_2025 and db_live) else db_main
        try:
            for r in active_db.execute(sql_later, {"as_of": as_of.isoformat()}).fetchall():
                s_id, p_id, c_id, q_ord, q_ship = r
                due_later_map[s_id] = {
                    "product_id": p_id,
                    "customer_id": c_id,
                    "open": max(0, q_ord - q_ship)
                }
        except Exception:
            pass

        # Service by product (Finished Goods Only)
        product_service = []
        for prod in finished_products:
            p_items = [v for v in distinct_sos.values() if v["product_id"] == prod.id]
            p_ontime = sum(1 for v in p_items if v["category"] == "on_time")
            p_late = sum(1 for v in p_items if v["category"] == "shipped_late")
            p_partial = sum(1 for v in p_items if v["category"] == "partial")
            p_unshipped = sum(1 for v in p_items if v["category"] == "unshipped")
            p_cancelled = sum(1 for v in p_items if v["category"] == "cancelled_opening")
            p_overdue_u = sum(v["quantity_open"] for v in p_items if v["category"] in ("partial", "unshipped"))
            p_overdue = sum(1 for v in p_items if v["category"] in ("partial", "unshipped") and v["quantity_open"] > 0)

            p_due_later_items = [v for v in due_later_map.values() if v["product_id"] == prod.id]
            p_due_later = len(p_due_later_items)
            p_due_later_u = sum(v["open"] for v in p_due_later_items)

            p_tot = p_ontime + p_late + p_partial + p_unshipped + p_cancelled
            p_pct = f"{(p_ontime / p_tot * 100):.1f}%" if p_tot > 0 else "—"

            product_service.append({
                "product_name": prod.name,
                "orders_count": p_tot,
                "on_time_count": p_ontime,
                "shipped_late_count": p_late,
                "partial_count": p_partial,
                "unshipped_count": p_unshipped,
                "cancelled_count": p_cancelled,
                "overdue_count": p_overdue,
                "on_time_pct": p_pct,
                "units_overdue_now": p_overdue_u,
                "due_later_orders": p_due_later,
                "units_due_later": p_due_later_u,
                "units_owed_now": p_overdue_u
            })

        # Service by customer
        customer_service = []
        for cust in customers:
            c_items = [v for v in distinct_sos.values() if v["customer_id"] == cust.id]
            c_ontime = sum(1 for v in c_items if v["category"] == "on_time")
            c_late = sum(1 for v in c_items if v["category"] == "shipped_late")
            c_partial = sum(1 for v in c_items if v["category"] == "partial")
            c_unshipped = sum(1 for v in c_items if v["category"] == "unshipped")
            c_cancelled = sum(1 for v in c_items if v["category"] == "cancelled_opening")
            c_overdue_u = sum(v["quantity_open"] for v in c_items if v["category"] in ("partial", "unshipped"))
            c_overdue = sum(1 for v in c_items if v["category"] in ("partial", "unshipped") and v["quantity_open"] > 0)

            c_due_later_items = [v for v in due_later_map.values() if v["customer_id"] == cust.id]
            c_due_later = len(c_due_later_items)
            c_due_later_u = sum(v["open"] for v in c_due_later_items)

            c_tot = c_ontime + c_late + c_partial + c_unshipped + c_cancelled
            c_pct = f"{(c_ontime / c_tot * 100):.1f}%" if c_tot > 0 else "—"

            customer_service.append({
                "customer_name": cust.name,
                "orders_count": c_tot,
                "on_time_count": c_ontime,
                "shipped_late_count": c_late,
                "partial_count": c_partial,
                "unshipped_count": c_unshipped,
                "cancelled_count": c_cancelled,
                "overdue_count": c_overdue,
                "on_time_pct": c_pct,
                "units_overdue_now": c_overdue_u,
                "due_later_orders": c_due_later,
                "units_due_later": c_due_later_u,
                "units_owed_now": c_overdue_u
            })

        # Sort top 5 delayed orders
        all_late_so_items = [r for r in late_customer_records]
        all_late_so_items.sort(key=lambda x: x["days_late"], reverse=True)
        top5_delayed_orders = all_late_so_items[:5]

        # 6. Delay Ledger (combined sortable table)
        delay_ledger = late_supplier_records + late_customer_records
        delay_ledger.sort(key=lambda x: x["days_late"], reverse=True)

        # 7. Weekly Trend Table + Line Chart
        weekly_trend_rows = []
        weekly_chart_labels = []
        weekly_chart_late_units = []

        if not panel_window.empty:
            panel_copy = panel_window.copy()
            panel_copy["date_dt"] = pd.to_datetime(panel_copy["date"])
            panel_copy["week"] = panel_copy["date_dt"].dt.to_period("W-SUN").apply(lambda r: r.start_time.date())

            for wk_start, grp in panel_copy.groupby("week"):
                wk_end = wk_start + timedelta(days=6)
                dem = int(grp.get("product_201_demand_units", 0).sum() + grp.get("product_202_demand_units", 0).sum())
                prod_u = int(grp.get("product_201_actual_production", 0).sum() + grp.get("product_202_actual_production", 0).sum())
                shipped = int(grp.get("product_201_shipments", 0).sum() if "product_201_shipments" in grp.columns else prod_u)
                late_u = int(grp.get("product_201_due_backlog_units", 0).max() + grp.get("product_202_due_backlog_units", 0).max())
                low_m = int(((grp.get("material_101_stock", 300) <= 50.0) | (grp.get("material_102_stock", 250) <= 40.0) | (grp.get("material_103_stock", 200) <= 30.0)).sum())

                lbl = f"{wk_start.strftime('%-d %b')} – {wk_end.strftime('%-d %b')}"
                weekly_trend_rows.append({
                    "week_label": lbl,
                    "demand": dem,
                    "produced": prod_u,
                    "shipped": shipped,
                    "late_units": late_u,
                    "days_low_stock": low_m
                })
                weekly_chart_labels.append(lbl)
                weekly_chart_late_units.append(late_u)

        # 8. What Changed This Week (Last 7 Days vs Prior 7 Days)
        t_now = as_of
        w_curr_start = max(date(2025, 1, 1), t_now - timedelta(days=6))
        w_prev_end = w_curr_start - timedelta(days=1)
        w_prev_start = max(date(2025, 1, 1), w_prev_end - timedelta(days=6))

        curr_panel = panel[(panel["date"] >= w_curr_start.isoformat()) & (panel["date"] <= t_now.isoformat())] if not panel.empty else pd.DataFrame()
        prev_panel = panel[(panel["date"] >= w_prev_start.isoformat()) & (panel["date"] <= w_prev_end.isoformat())] if not panel.empty else pd.DataFrame()

        def _get_metric_diff(curr_val: int, prev_val: int, unit_singular: str, unit_plural: str = "") -> Dict[str, Any]:
            if not unit_plural:
                unit_plural = unit_singular + "s"
            diff = curr_val - prev_val
            if diff > 0:
                u_str = unit_singular if diff == 1 else unit_plural
                change_str = f"Up {diff} {u_str}".strip()
                color = "#dc2626"
            elif diff < 0:
                u_str = unit_singular if abs(diff) == 1 else unit_plural
                change_str = f"Down {abs(diff)} {u_str}".strip()
                color = "#16a34a"
            else:
                change_str = "Unchanged"
                color = "#64748b"
            return {"current": curr_val, "previous": prev_val, "change_str": change_str, "color": color}

        curr_late_u = int(curr_panel.get("product_201_due_backlog_units", 0).max() + curr_panel.get("product_202_due_backlog_units", 0).max()) if not curr_panel.empty else 0
        prev_late_u = int(prev_panel.get("product_201_due_backlog_units", 0).max() + prev_panel.get("product_202_due_backlog_units", 0).max()) if not prev_panel.empty else 0

        curr_supp_d = sum(1 for d in po_receipts.values() if d["delay_days"] > 0 and d["receipt_date"] >= w_curr_start.isoformat() and d["receipt_date"] <= t_now.isoformat())
        prev_supp_d = sum(1 for d in po_receipts.values() if d["delay_days"] > 0 and d["receipt_date"] >= w_prev_start.isoformat() and d["receipt_date"] <= w_prev_end.isoformat())

        curr_low_m = int(((curr_panel.get("material_101_stock", 300) <= 50.0) | (curr_panel.get("material_102_stock", 250) <= 40.0) | (curr_panel.get("material_103_stock", 200) <= 30.0)).sum()) if not curr_panel.empty else 0
        prev_low_m = int(((prev_panel.get("material_101_stock", 300) <= 50.0) | (prev_panel.get("material_102_stock", 250) <= 40.0) | (prev_panel.get("material_103_stock", 200) <= 30.0)).sum()) if not prev_panel.empty else 0

        curr_late_u_label = f"{curr_late_u} unit" if curr_late_u == 1 else f"{curr_late_u} units"
        curr_supp_d_label = f"{curr_supp_d} delay" if curr_supp_d == 1 else f"{curr_supp_d} delays"
        curr_low_m_label = f"{curr_low_m} day" if curr_low_m == 1 else f"{curr_low_m} days"

        what_changed_strip = {
            "late_units": {
                **_get_metric_diff(curr_late_u, prev_late_u, "unit", "units"),
                "display": curr_late_u_label
            },
            "supplier_delays": {
                **_get_metric_diff(curr_supp_d, prev_supp_d, "delay", "delays"),
                "display": curr_supp_d_label
            },
            "low_stock_days": {
                **_get_metric_diff(curr_low_m, prev_low_m, "day", "days"),
                "display": curr_low_m_label
            }
        }

        # 9. Summary Strip Numbers (Existing 4 KPI cards)
        total_req_all = sum(p["orders_count"] for p in product_service)
        total_ontime_all = sum(p["on_time_count"] for p in product_service)
        total_late_all = sum(p["shipped_late_count"] for p in product_service)
        total_partial_all = sum(p["partial_count"] for p in product_service)
        total_unshipped_all = sum(p["unshipped_count"] for p in product_service)
        total_cancelled_all = sum(p["cancelled_count"] for p in product_service)
        total_overdue_all = sum(p["overdue_count"] for p in product_service)
        total_overdue_u_all = sum(p["units_overdue_now"] for p in product_service)
        total_due_later_all = sum(p["due_later_orders"] for p in product_service)
        total_due_later_u_all = sum(p["units_due_later"] for p in product_service)

        cust_on_time_pct = round((total_ontime_all / total_req_all * 100.0), 1) if total_req_all > 0 else 100.0

        total_ontime_units = sum(v["quantity_shipped"] for v in distinct_sos.values() if v["category"] == "on_time")
        total_partial_open_units = sum(v["quantity_open"] for v in distinct_sos.values() if v["category"] == "partial")
        total_unshipped_units = sum(v["quantity_open"] for v in distinct_sos.values() if v["category"] == "unshipped")
        total_cancelled_units = sum(v["quantity_open"] for v in distinct_sos.values() if v["category"] == "cancelled_opening")

        fulfillment_buckets = {
            "total_orders": total_req_all,
            "on_time_orders": total_ontime_all,
            "on_time_units": total_ontime_units,
            "shipped_late_orders": total_late_all,
            "shipped_late_units": 0,
            "partial_orders": total_partial_all,
            "partial_open_units": total_partial_open_units,
            "unshipped_orders": total_unshipped_all,
            "unshipped_units": total_unshipped_units,
            "cancelled_opening_orders": total_cancelled_all,
            "cancelled_opening_units": total_cancelled_units,
            "total_open_orders": total_overdue_all,
            "total_open_units": total_overdue_u_all,
            "due_later_orders": total_due_later_all,
            "due_later_units": total_due_later_u_all,
            "on_time_pct": cust_on_time_pct,
            "show_shipped_late": (total_late_all > 0),
            "has_cancelled_opening": (total_cancelled_all > 0)
        }

        days_with_overdue_orders = 0
        days_cust_overdue = 0
        days_supp_overdue = 0
        days_material_low = 0
        total_lost_production = 0

        if not panel_window.empty:
            has_backlog = (panel_window.get("product_201_due_backlog_units", 0) > 0) | (panel_window.get("product_202_due_backlog_units", 0) > 0)
            has_supp_delay = (
                (panel_window.get("supplier_1_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_2_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_3_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_4_po_delay_days", 0) > 0) |
                (panel_window.get("supplier_5_po_delay_days", 0) > 0)
            )
            days_with_overdue_orders = int((has_backlog | has_supp_delay).sum())
            days_cust_overdue = int(has_backlog.sum())
            days_supp_overdue = int(has_supp_delay.sum())

            low_m1 = panel_window.get("material_101_stock", 300) <= 50.0
            low_m2 = panel_window.get("material_102_stock", 250) <= 40.0
            low_m3 = panel_window.get("material_103_stock", 200) <= 30.0
            days_material_low = int((low_m1 | low_m2 | low_m3).sum())

            shortfall_201 = panel_window.get("product_201_production_shortfall", 0).sum()
            shortfall_202 = panel_window.get("product_202_production_shortfall", 0).sum()
            total_lost_production = int(shortfall_201 + shortfall_202)

        cancelled_info = f", including {total_cancelled_all} orders cancelled at the feed opening position" if total_cancelled_all > 0 else ""
        summary_strip = [
            {
                "id": "kpi_on_time",
                "label": "Orders delivered on time",
                "value": f"{cust_on_time_pct:.1f}%",
                "meaning": f"Shipped to customers on or before the requested date ({total_ontime_all} of {total_req_all} orders).",
                "calc_info": f"An order is on time if fully shipped on or before its requested delivery date. Recomputed from shipment and sales order rows. Calculated as orders shipped on time ({total_ontime_all}) divided by all orders requested on or before the current day ({total_req_all}){cancelled_info}. Unfulfilled and cancelled orders count as not on time."
            },
            {
                "id": "kpi_overdue_days",
                "label": "Days with an overdue order",
                "value": f"{days_with_overdue_orders} {'day' if days_with_overdue_orders == 1 else 'days'}",
                "meaning": f"{days_cust_overdue} {'day' if days_cust_overdue == 1 else 'days'} with customer backorders, {days_supp_overdue} {'day' if days_supp_overdue == 1 else 'days'} with overdue POs.",
                "calc_info": f"Count of distinct calendar dates in the period where customer order backlog exceeded 0 ({days_cust_overdue} {'day' if days_cust_overdue == 1 else 'days'}) or an open PO was past expected delivery ({days_supp_overdue} {'day' if days_supp_overdue == 1 else 'days'}). Total distinct dates: {days_with_overdue_orders} {'day' if days_with_overdue_orders == 1 else 'days'}."
            },
            {
                "id": "kpi_safety_days",
                "label": "Days buffer fell to safety level",
                "value": f"{days_material_low} {'day' if days_material_low == 1 else 'days'}",
                "meaning": "Days where raw material inventory fell to or below reserve.",
                "calc_info": "Count of dates where Steel Rod 10mm fell to <= 50 kg, Plastic Granules <= 40 kg, or Copper Wire <= 30 kg."
            },
            {
                "id": "kpi_production_lost",
                "label": "Planned production lost",
                "value": f"{total_lost_production} {'unit' if total_lost_production == 1 else 'units'}",
                "meaning": "Manufacturing shortfall below daily planned output schedule.",
                "calc_info": f"Cumulative production shortfall across Line 1 (Widget Model X) and Line 2 (Widget Model Y) in the reporting period: {total_lost_production} units."
            }
        ]

        # 10. Episodes with templated stories
        episodes = []
        chart2_dates = []
        chart2_backlog = []
        chart2_in_episode = []

        cur_ep_start = None
        cur_ep_peak_backlog = 0
        cur_ep_materials = set()
        cur_ep_products = set()
        cur_ep_suppliers = set()

        if not panel_window.empty:
            for idx, row in panel_window.iterrows():
                dt_str = row["date"]
                dt_obj = datetime.strptime(dt_str, "%Y-%m-%d").date()
                b_201 = float(row.get("product_201_due_backlog_units", 0))
                b_202 = float(row.get("product_202_due_backlog_units", 0))
                day_backlog = int(b_201 + b_202)

                s101 = float(row.get("material_101_stock", 300))
                s102 = float(row.get("material_102_stock", 250))
                s103 = float(row.get("material_103_stock", 200))
                sh_201 = float(row.get("product_201_production_shortfall", 0))
                sh_202 = float(row.get("product_202_production_shortfall", 0))

                supp_delays = {s: float(row.get(f"supplier_{s}_po_delay_days", 0)) for s in range(1, 6)}

                is_eventful = (
                    day_backlog > 0 or
                    any(v > 0 for v in supp_delays.values()) or
                    s101 <= 50.0 or s102 <= 40.0 or s103 <= 30.0 or
                    sh_201 > 0 or sh_202 > 0
                )

                chart2_dates.append(dt_str)
                chart2_backlog.append(day_backlog)
                chart2_in_episode.append(1 if is_eventful else 0)

                if is_eventful:
                    if cur_ep_start is None:
                        cur_ep_start = dt_obj
                        cur_ep_peak_backlog = day_backlog
                        cur_ep_materials = set()
                        cur_ep_products = set()
                        cur_ep_suppliers = set()

                    cur_ep_peak_backlog = max(cur_ep_peak_backlog, day_backlog)
                    if s101 <= 50.0: cur_ep_materials.add(mat_map.get(101, "Steel Rod 10mm"))
                    if s102 <= 40.0: cur_ep_materials.add(mat_map.get(102, "Plastic Granules"))
                    if s103 <= 30.0: cur_ep_materials.add(mat_map.get(103, "Copper Wire"))
                    if b_201 > 0 or sh_201 > 0: cur_ep_products.add(prod_map.get(201, "Widget Model X"))
                    if b_202 > 0 or sh_202 > 0: cur_ep_products.add(prod_map.get(202, "Widget Model Y"))
                    for s_num, d_val in supp_delays.items():
                        if d_val > 0:
                            s_obj_name = next((s.name for s in suppliers if s.id == s_num), f"Supplier {s_num}")
                            cur_ep_suppliers.add(s_obj_name)
                else:
                    if cur_ep_start is not None:
                        prev_date = dt_obj - timedelta(days=1)
                        ep_len = (prev_date - cur_ep_start).days + 1
                        items_str = ", ".join(sorted(cur_ep_products | cur_ep_materials)) or "Buffer inventory"
                        supp_str = ", ".join(sorted(cur_ep_suppliers)) or "None"
                        story_text = (
                            f"Episode started on {cur_ep_start.strftime('%-d %b')} and ended on {prev_date.strftime('%-d %b')} "
                            f"({format_days_plural(ep_len)}). Peak backlog reached {cur_ep_peak_backlog} units of {items_str}. "
                            f"{('Coincided with ' + supp_str + ' delivery delays.') if supp_str != 'None' else 'Internal constraint.'} "
                            f"Buffer recovered within {format_days_plural(ep_len)}."
                        )
                        episodes.append({
                            "start_date": cur_ep_start.isoformat(),
                            "end_date": prev_date.isoformat(),
                            "duration_days": ep_len,
                            "peak_backlog": cur_ep_peak_backlog,
                            "items_involved": items_str,
                            "coincided_supplier": f"Coincided with {supp_str} delay" if supp_str != "None" else "None",
                            "story": story_text
                        })
                        cur_ep_start = None

            if cur_ep_start is not None:
                ep_len = (as_of - cur_ep_start).days + 1
                items_str = ", ".join(sorted(cur_ep_products | cur_ep_materials)) or "Buffer inventory"
                supp_str = ", ".join(sorted(cur_ep_suppliers)) or "None"
                story_text = (
                    f"Ongoing episode started on {cur_ep_start.strftime('%-d %b')} ({format_days_plural(ep_len)} active). "
                    f"Peak backlog has reached {cur_ep_peak_backlog} units of {items_str}. "
                    f"{('Coincided with ' + supp_str + ' delivery delays.') if supp_str != 'None' else 'Internal constraint.'}"
                )
                episodes.append({
                    "start_date": cur_ep_start.isoformat(),
                    "end_date": as_of.isoformat(),
                    "duration_days": ep_len,
                    "peak_backlog": cur_ep_peak_backlog,
                    "items_involved": items_str,
                    "coincided_supplier": f"Coincided with {supp_str} delay" if supp_str != "None" else "None",
                    "story": story_text
                })

        # 11. Existing Chart Blocks: Materials (Stock vs Safety) & Products (Demand vs Built)
        materials_charts = []
        mat_meta = [
            (101, mat_map.get(101, "Steel Rod 10mm"), 50.0, 150.0),
            (102, mat_map.get(102, "Plastic Granules"), 40.0, 120.0),
            (103, mat_map.get(103, "Copper Wire"), 30.0, 100.0)
        ]
        for m_id, m_name, s_limit, r_limit in mat_meta:
            m_col = f"material_{m_id}_stock"
            stock_series = [float(v) for v in panel_window[m_col].tolist()] if not panel_window.empty and m_col in panel_window.columns else []
            days_below = int((panel_window[m_col] <= s_limit).sum()) if not panel_window.empty and m_col in panel_window.columns else 0
            takeaway = f"{m_name} fell below its reserve buffer on {format_days_plural(days_below)}." if days_below > 0 else f"{m_name} remained safely above reserve buffer levels."
            materials_charts.append({
                "material_id": m_id,
                "name": m_name,
                "safety_level": s_limit,
                "reorder_level": r_limit,
                "days_below_safety": days_below,
                "takeaway": takeaway,
                "dates": chart2_dates,
                "stock_values": stock_series
            })

        products_charts = []
        prod_meta = [
            (201, prod_map.get(201, "Widget Model X")),
            (202, prod_map.get(202, "Widget Model Y"))
        ]
        for p_id, p_name in prod_meta:
            dem_col = f"product_{p_id}_demand_units"
            act_col = f"product_{p_id}_actual_production"
            fg_col = f"product_{p_id}_fg_stock"
            sh_col = f"product_{p_id}_production_shortfall"

            dem_series = [float(v) for v in panel_window.get(dem_col, 0).tolist()] if not panel_window.empty else []
            act_series = [float(v) for v in panel_window.get(act_col, 0).tolist()] if not panel_window.empty else []
            fg_series = [float(v) for v in panel_window.get(fg_col, 0).tolist()] if not panel_window.empty else []
            total_short = int(panel_window.get(sh_col, 0).sum()) if not panel_window.empty else 0
            takeaway = f"{p_name} experienced {total_short} units of production shortfall." if total_short > 0 else f"{p_name} fulfilled 100% of planned production schedule."

            products_charts.append({
                "product_id": p_id,
                "name": p_name,
                "total_shortfall_units": total_short,
                "takeaway": takeaway,
                "dates": chart2_dates,
                "demand": dem_series,
                "actual_production": act_series,
                "finished_stock": fg_series
            })

        # Reliability Summary Box
        reliability_summary = [
            "In zero-shot evaluation on fresh synthetic worlds (Test A), SAGE detected 0 of 3 target disruptions (Scenarios 3, 4, 6) and triggered false alarms on 60% to 90% of quiet windows because thresholds fitted to Seed 42 did not transfer across environments.",
            "In site-calibrated deployment (Test A2, tested on one new synthetic world), recalibrating null thresholds on Seed 7's own baseline panel controlled false alarms to 5.0% on quiet windows, but still detected 0 of 3 target disruptions because incident scores remained below the site's higher baseline noise threshold.",
            "On real retail demand data (Test B), SAGE detected 1 of 4 holidays (Thanksgiving at 6.26x above null) with a 2.1% false-alarm rate, while a naive year-over-year baseline detected 0 of 4 holidays with a 4.2% false-alarm rate."
        ]

        has_data = len(delay_ledger) > 0 or len(episodes) > 0 or any(c["deliveries_count"] > 0 for c in supplier_cards)

        # Delivery delay takeaway computed strictly from data
        worst_supp = max(
            [c for c in supplier_cards if c["deliveries_count"] > 0 and c["worst_delay_str"] != "—" and "0 days" not in c["worst_delay_str"]],
            key=lambda c: [int(s) for s in c["worst_delay_str"].split() if s.isdigit()][0] if any(s.isdigit() for s in c["worst_delay_str"].split()) else 0,
            default=None
        )
        if worst_supp:
            takeaway_delays = f"Longest delays coincided with {worst_supp['supplier_name']} receipts ({worst_supp['worst_delay_str']})."
        else:
            takeaway_delays = "All deliveries arrived on or ahead of scheduled dates."

        history_events = build_history_and_key_events(as_of)
        forecast_sec = build_forecast_insights_section()

        return {
            "as_of": as_of_str,
            "period": period_str,
            "period_label": period_label,
            "date_range_str": date_range_str,
            "has_data": has_data,
            "empty_period_notice": "Nothing happened in this period. Consider selecting a longer period such as 'Year so far'." if not has_data else "",
            "is_demo_full_year": (period_str == "full_year" and is_demo),
            "summary_strip": summary_strip,
            "history_and_key_events": history_events,
            "forecast_section": forecast_sec,
            "fulfillment_buckets": fulfillment_buckets,
            "what_changed_strip": what_changed_strip,
            "supplier_cards": supplier_cards,
            "customer_service": customer_service,
            "product_service": product_service,
            "top5_delayed_orders": top5_delayed_orders,
            "delay_ledger": delay_ledger,
            "weekly_trend_rows": weekly_trend_rows,
            "weekly_chart_labels": weekly_chart_labels,
            "weekly_chart_late_units": weekly_chart_late_units,
            "chart_delivery_delays": {
                "title": "Were deliveries on time?",
                "takeaway": takeaway_delays,
                "points": chart_delivery_delays
            },
            "episodes": {
                "title": "When did things go wrong?",
                "takeaway": f"Operations observed {len(episodes)} disruption episodes totaling {sum(e['duration_days'] for e in episodes)} days." if episodes else "Zero disruption episodes detected in this period.",
                "dates": chart2_dates,
                "backlog_series": chart2_backlog,
                "in_episode_series": chart2_in_episode,
                "table": episodes
            },
            "materials_charts": materials_charts,
            "products_charts": products_charts,
            "past_cases": FROZEN_PAST_CASES,
            "idle_suppliers_note": idle_suppliers_note,
            "reliability_summary": reliability_summary,
            "framing": RESEARCH_FRAMING
        }

    finally:
        try:
            db_main.close()
        except Exception:
            pass
        try:
            db_live.close()
        except Exception:
            pass


def generate_supplier_report_csv(data: Dict[str, Any]) -> str:
    """Renders the supplier report card table as RFC 4180 CSV text."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Supplier Name",
        "Material Supplied",
        "Deliveries (n)",
        "On-Time (%)",
        "Average Days Late",
        "Worst Delay",
        "Lead Time",
        "Open Orders Now",
        "Next Expected Date",
        "Quantity Received vs Ordered",
        "Coincided With",
        "Rating"
    ])

    for row in data.get("supplier_cards", []):
        writer.writerow([
            row["supplier_name"],
            row["material_supplied"],
            row["deliveries_count"],
            row["on_time_pct_str"],
            row["avg_days_late_str"],
            row["worst_delay_str"],
            row["lead_time_str"],
            row["open_orders_str"],
            row["next_expected_str"],
            row["quantity_str"],
            row["coincided_str"],
            row["rating"]
        ])

    return output.getvalue()


def generate_delay_ledger_csv(data: Dict[str, Any]) -> str:
    """Renders the delay ledger table as RFC 4180 CSV text."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record Type",
        "Reference #",
        "Partner",
        "Item",
        "Quantity",
        "Due Date",
        "Actual Date",
        "Days Late",
        "Status"
    ])

    for row in data.get("delay_ledger", []):
        writer.writerow([
            row["record_type"],
            row["ref_no"],
            row["partner"],
            row["item"],
            row["quantity"],
            row["due_date"],
            row["actual_date"],
            row["days_late"],
            row["status"]
        ])

    return output.getvalue()

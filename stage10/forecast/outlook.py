"""
stage10/forecast/outlook.py — SAGE Weekly Order Forward-Look Engine.

Guarantees:
- Zero look-ahead: At day D, features read only records <= D.
- Pre-registered selection: Deployed Model 2 (Trailing 28d Mean x 7).
- Past-day rule: When viewing a past day, returns forecast ONLY if stored in
  stage10/forecast/outputs/test_weekly_forecasts.json; otherwise "No forecast stored for this day".
- Shortage risk wording strictly: "Low", "Medium", "High".
- Mandatory research framing verbatim.
"""

from __future__ import annotations

import json
import pickle
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.snapshot import compute_daily_snapshot, load_rules
from stage9.status import RESEARCH_FRAMING

OUTPUTS_DIR = ROOT_DIR / "stage10" / "forecast" / "outputs"
TEST_FORECASTS_PATH = OUTPUTS_DIR / "test_weekly_forecasts.json"
METRICS_PATH = OUTPUTS_DIR / "metrics.json"

_STORED_FORECASTS: Optional[Dict[str, Any]] = None
_METRICS_DATA: Optional[Dict[str, Any]] = None
_OUTLOOK_CACHE: Dict[str, Dict[str, Any]] = {}


def load_stored_forecasts() -> Dict[str, Any]:
    global _STORED_FORECASTS
    if _STORED_FORECASTS is not None:
        return _STORED_FORECASTS
    if TEST_FORECASTS_PATH.exists():
        try:
            with open(TEST_FORECASTS_PATH, "r", encoding="utf-8") as f:
                _STORED_FORECASTS = json.load(f)
                return _STORED_FORECASTS
        except Exception:
            return {}
    return {}


def load_metrics_data() -> Dict[str, Any]:
    global _METRICS_DATA
    if _METRICS_DATA is not None:
        return _METRICS_DATA
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                _METRICS_DATA = json.load(f)
                return _METRICS_DATA
        except Exception:
            return {}
    return {}


def generate_mini_forecast_chart_svg(test_forecasts: Dict[str, Any], n_weeks: int = 12) -> str:
    """Generates a clean SVG bar/sparkline comparing actual vs forecast for trailing weeks."""
    sorted_dates = sorted(test_forecasts.keys())
    recent_dates = sorted_dates[-n_weeks:]
    if not recent_dates:
        return ""

    width = 240
    height = 50
    pad_x = 10
    pad_y = 6

    vals = []
    for d in recent_dates:
        entry = test_forecasts[d]
        pred = entry.get("expected_new_orders", 0)
        act = entry.get("actual_realized", 0)
        vals.extend([pred, act])

    max_v = max(vals) if vals and max(vals) > 0 else 100.0
    bar_w = (width - 2 * pad_x) / (len(recent_dates) * 2.5)

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" class="forecast-sparkline-svg" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;height:auto;">'
    ]

    for i, d in enumerate(recent_dates):
        entry = test_forecasts[d]
        pred = entry.get("expected_new_orders", 0)
        act = entry.get("actual_realized", 0)

        x_group = pad_x + i * 2.5 * bar_w
        # Actual bar (dark blue)
        h_act = (act / max_v) * (height - 2 * pad_y)
        y_act = height - pad_y - h_act
        svg_parts.append(f'<rect x="{x_group:.1f}" y="{y_act:.1f}" width="{bar_w:.1f}" height="{h_act:.1f}" fill="#3b82f6" rx="1" opacity="0.85"><title>{d} Actual: {act}u</title></rect>')

        # Forecast bar (light blue dashed outline or lighter blue)
        h_pred = (pred / max_v) * (height - 2 * pad_y)
        y_pred = height - pad_y - h_pred
        svg_parts.append(f'<rect x="{x_group + bar_w + 1:.1f}" y="{y_pred:.1f}" width="{bar_w:.1f}" height="{h_pred:.1f}" fill="#93c5fd" rx="1"><title>{d} Forecast: {pred}u</title></rect>')

    svg_parts.append('</svg>')
    return "".join(svg_parts)


def get_weekly_forecast(
    as_of: date,
    is_past_day: bool = False,
    db_session=None,
    use_cache: bool = True,
    rules: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes weekly forecast for as_of date.
    Strictly adheres to past-day rule and zero look-ahead.
    """
    if rules is None:
        rules = load_rules()

    outlook_cfg = rules.get("outlook", {})
    if not outlook_cfg.get("enabled", True):
        return {"available": False, "message": "Forecast disabled by configuration", "framing": RESEARCH_FRAMING}

    as_of_str = as_of.isoformat()
    cache_key = f"{as_of_str}_{is_past_day}"
    if use_cache and cache_key in _OUTLOOK_CACHE:
        return _OUTLOOK_CACHE[cache_key]

    stored_fc = load_stored_forecasts()
    metrics = load_metrics_data()
    m_info = metrics.get("metadata", {})
    p_tot = metrics.get("per_product_test", {}).get("total", {})
    model_name = m_info.get("deployed_model_name", "Trailing 28d Mean x 7")
    wape_pct = round(p_tot.get("wape", 0.6474) * 100, 1)
    mae_units = round(p_tot.get("mae", 31.1), 1)
    test_n = p_tot.get("n", 25)

    b_x = 0
    b_y = 0

    # 1. Past-Day Rule Check
    if is_past_day:
        if as_of_str in stored_fc:
            fc_entry = stored_fc[as_of_str]
            pred_pt = fc_entry["expected_new_orders"]
            q10 = fc_entry["range_low"]
            q90 = fc_entry["range_high"]
            due_k = fc_entry["due_known"]
            b_x = int(round(due_k * 0.55))
            b_y = due_k - b_x
            is_stored = True
        else:
            res = {
                "available": False,
                "is_past_day": True,
                "as_of": as_of_str,
                "message": "No forecast stored for this day",
                "framing": RESEARCH_FRAMING
            }
            if use_cache:
                _OUTLOOK_CACHE[cache_key] = res
            return res
    else:
        # Live simulated day calculation
        is_stored = False
        source = "live" if as_of.year >= 2026 else "main"
        close_sess = False
        if db_session is None:
            from app.database import SessionLocal
            db_session = SessionLocal(source=source)
            close_sess = True

        try:
            from app.models.sales import SalesOrder, SalesOrderLine
            # Trailing 28 days of new sales ordered up to as_of
            d_start_28 = as_of - timedelta(days=28)
            t28_units = (
                db_session.query(SalesOrderLine.quantity_ordered)
                .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
                .filter(
                    SalesOrder.order_date > d_start_28,
                    SalesOrder.order_date <= as_of,
                    SalesOrder.status != "Cancelled"
                )
                .all()
            )
            sum_28 = sum(r[0] for r in t28_units if r[0])
            pred_pt = round((sum_28 / 28.0) * 7.0, 1)
            q10 = round(max(0.0, pred_pt * 0.55), 1)
            q90 = round(pred_pt * 1.50, 1)

            # Known orders already due in D+1..D+7 by product
            d_next_1 = as_of + timedelta(days=1)
            d_next_7 = as_of + timedelta(days=7)
            due_records = (
                db_session.query(SalesOrderLine.product_id, SalesOrderLine.quantity_ordered)
                .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
                .filter(
                    SalesOrder.order_date <= as_of,
                    SalesOrder.requested_delivery_date >= d_next_1,
                    SalesOrder.requested_delivery_date <= d_next_7,
                    SalesOrder.status != "Cancelled"
                )
                .all()
            )
            due_k = int(sum(r[1] for r in due_records if r[1]))
            b_x = int(sum(r[1] for r in due_records if r[0] == 201 and r[1]))
            b_y = int(sum(r[1] for r in due_records if r[0] == 202 and r[1]))
        finally:
            if close_sess:
                db_session.close()

    # Horizon display
    h_start = (as_of + timedelta(days=1)).strftime("%-d %b")
    h_end = (as_of + timedelta(days=7)).strftime("%-d %b")
    horizon_str = f"{h_start}–{h_end}"

    # Shortage risk calculation (strictly "Low", "Medium", "High")
    # Buffer = Finished Goods stock + planned weekly capacity (50u/day * 5 weekdays = 250u) - known due orders
    source = "live" if as_of.year >= 2026 else "main"
    snap = compute_daily_snapshot(as_of, source=source)
    fg_stock = sum(float(p.get("fg_stock", 15.0)) for p in snap.get("products", {}).values())
    projected_weekly_buffer = fg_stock + 250.0 - due_k

    if projected_weekly_buffer < 0:
        shortage_risk = "High"
        shortage_badge = "critical"
        shortage_color = "#ef4444"
        shortage_desc = f"Projected shortage of {int(abs(projected_weekly_buffer))} units vs committed deliveries"
    elif projected_weekly_buffer < 50.0:
        shortage_risk = "Medium"
        shortage_badge = "attention"
        shortage_color = "#f59e0b"
        shortage_desc = f"Projected buffer ({int(projected_weekly_buffer)} units) below weekly safety margin (50 units)"
    else:
        shortage_risk = "Low"
        shortage_badge = "normal"
        shortage_color = "#10b981"
        shortage_desc = f"Finished goods buffer of {int(projected_weekly_buffer)} units comfortably covers commitments"

    sparkline_svg = generate_mini_forecast_chart_svg(stored_fc, n_weeks=12)

    exp_new = int(round(pred_pt))
    lo = int(round(q10))
    hi = int(round(q90))
    tot_due = due_k + exp_new
    tot_lo = due_k + lo
    tot_hi = due_k + hi

    new_x = int(round(exp_new * 0.55))
    new_y = exp_new - new_x
    tot_x = b_x + new_x
    tot_y = b_y + new_y

    headline = f"Next 7 days: expected demand ~{tot_due} units due (likely range {tot_lo}–{tot_hi})"
    breakdown_line = f"{due_k} already booked + ~{exp_new} expected new orders"
    product_breakdown = f"Widget Model X: ~{tot_x}u due ({b_x} booked + ~{new_x} new) | Widget Model Y: ~{tot_y}u due ({b_y} booked + ~{new_y} new)"

    result = {
        "available": True,
        "is_past_day": is_past_day,
        "is_stored": is_stored,
        "as_of": as_of_str,
        "horizon": horizon_str,
        "total_demand_due": tot_due,
        "range_low": tot_lo,
        "range_high": tot_hi,
        "expected_new_orders": exp_new,
        "new_orders_range_low": lo,
        "new_orders_range_high": hi,
        "due_known": due_k,
        "headline": headline,
        "breakdown_line": breakdown_line,
        "product_breakdown": product_breakdown,
        "sparkline_svg": sparkline_svg,
        "shortage_risk": shortage_risk,
        "shortage_badge": shortage_badge,
        "shortage_color": shortage_color,
        "shortage_desc": shortage_desc,
        "model_name": model_name,
        "wape_pct": wape_pct,
        "mae_units": mae_units,
        "test_n": test_n,
        "framing": RESEARCH_FRAMING
    }

    if use_cache:
        _OUTLOOK_CACHE[cache_key] = result

    return result


def clear_outlook_cache():
    global _OUTLOOK_CACHE
    _OUTLOOK_CACHE.clear()

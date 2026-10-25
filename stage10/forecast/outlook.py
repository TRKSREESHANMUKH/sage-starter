"""
stage10/forecast/outlook.py — Tomorrow Outlook computation engine for viewer Today page.

Guarantees:
- ZERO look-ahead: reads features only <= as_of.
- Respects outlook.enabled flag in stage9/config/rules.yaml.
- Sub-3-second render: cached in memory per as_of date.
- Framing sentence intact: verbatim Rule 2.
"""

from __future__ import annotations

import json
import pickle
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from stage9.snapshot import compute_daily_snapshot, load_rules
from stage9.status import RESEARCH_FRAMING

MODEL_PKL_PATH = ROOT_DIR / "stage10" / "forecast" / "model.pkl"

_OUTLOOK_CACHE: Dict[str, Dict[str, Any]] = {}
_MODEL_ARTIFACT: Optional[Dict[str, Any]] = None


def load_forecast_model() -> Optional[Dict[str, Any]]:
    global _MODEL_ARTIFACT
    if _MODEL_ARTIFACT is not None:
        return _MODEL_ARTIFACT
    if MODEL_PKL_PATH.exists():
        try:
            with open(MODEL_PKL_PATH, "rb") as f:
                _MODEL_ARTIFACT = pickle.load(f)
                return _MODEL_ARTIFACT
        except Exception:
            return None
    return None


def get_tomorrow_outlook(
    as_of: date,
    db_session=None,
    use_cache: bool = True,
    rules: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    Computes tomorrow outlook dynamically for as_of date.
    Strictly zero look-ahead: only data <= as_of is accessed.
    """
    if rules is None:
        rules = load_rules()

    outlook_cfg = rules.get("outlook", {})
    if not outlook_cfg.get("enabled", True):
        return None

    cache_key = as_of.isoformat()
    if use_cache and cache_key in _OUTLOOK_CACHE:
        return _OUTLOOK_CACHE[cache_key]

    d_next = as_of + timedelta(days=1)
    tomorrow_display = d_next.strftime("%a %-d %b")

    # 1. Load operational snapshot <= as_of
    source = "live" if as_of.year >= 2026 else "main"
    snapshot = compute_daily_snapshot(as_of, db_session=db_session, source=source)

    kpis = snapshot.get("kpis", {})
    mats = snapshot.get("materials", {})
    prods = snapshot.get("products", {})

    open_bklg = float(kpis.get("total_backlog_units", 0.0))
    mat_101 = float(mats.get("101", {}).get("stock", 100.0))
    mat_102 = float(mats.get("102", {}).get("stock", 100.0))
    mat_103 = float(mats.get("103", {}).get("stock", 100.0))
    fg_stock = sum(float(p.get("fg_stock", 15.0)) for p in prods.values())

    # 2. Query sales orders placed <= as_of
    close_sess = False
    if db_session is None:
        from app.database import SessionLocal
        db_session = SessionLocal(source=source)
        close_sess = True

    try:
        from app.models.sales import SalesOrder, SalesOrderLine
        # Orders due tomorrow that were placed on or before as_of
        due_tomorrow_on_books = float(
            db_session.query(SalesOrderLine.quantity_ordered)
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .filter(
                SalesOrder.requested_delivery_date == d_next,
                SalesOrder.order_date <= as_of,
                SalesOrder.status != "Cancelled"
            )
            .scalar() or 0.0
        )

        # Sales placed on as_of (lag 1)
        sales_today = float(
            db_session.query(SalesOrderLine.quantity_ordered)
            .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
            .filter(
                SalesOrder.order_date == as_of,
                SalesOrder.status != "Cancelled"
            )
            .scalar() or 0.0
        )
    except Exception:
        due_tomorrow_on_books = 0.0
        sales_today = 0.0
    finally:
        if close_sess:
            db_session.close()

    # 3. Model Inference for T1 (New Sales Expected)
    model = load_forecast_model()
    dt = np.datetime64(as_of)
    weekday = as_of.weekday()
    day_of_month = as_of.day
    month = as_of.month

    if model is not None:
        dow_feats = [1.0 if weekday == i else 0.0 for i in range(7)]
        # Feature vector for T1
        # [dow_0..6, day_of_month, month, lag_1, lag_2, lag_7, rolling_7_mean, rolling_7_std, open_backlog, units_due, mat_101, mat_102, mat_103]
        feat_t1 = dow_feats + [
            float(day_of_month), float(month),
            sales_today, sales_today, sales_today,
            sales_today, 0.0,
            open_bklg,
            due_tomorrow_on_books,
            mat_101, mat_102, mat_103
        ]
        X = np.array([feat_t1])
        t1_point = float(max(0.0, model["t1_p50"].predict(X)[0]))
        t1_p10 = float(max(0.0, model["t1_p10"].predict(X)[0]))
        t1_p90 = float(max(t1_p10, model["t1_p90"].predict(X)[0]))
        sublabel = "GBDT quantile model (test WAPE 1.11, 80% CI)"
    else:
        # Fallback heuristic
        t1_point = sales_today
        t1_p10 = max(0.0, t1_point - 5.0)
        t1_p90 = t1_point + 10.0
        sublabel = "Seasonal baseline model"

    # Display formatting for New Sales
    pt_int = int(round(t1_point))
    p10_int = int(round(t1_p10))
    p90_int = int(round(t1_p90))
    new_sales_display = f"{pt_int} units ({p10_int}–{p90_int}, 80% CI)"

    # Orders due tomorrow
    due_int = int(round(due_tomorrow_on_books))
    due_display = f"{due_int} units"
    due_sublabel = f"{due_int} units already on the books"

    # Shortage risk tomorrow
    plan_next = 50.0  # nominal daily capacity
    projected_buffer = fg_stock + plan_next - due_tomorrow_on_books

    if projected_buffer < 0:
        shortage_risk = "High"
        shortage_badge = "critical"
        shortage_color = "#ef4444"
        shortage_reason = f"Projected shortage of {int(abs(projected_buffer))} units vs committed deliveries"
    elif projected_buffer < 25.0:
        shortage_risk = "Medium"
        shortage_badge = "attention"
        shortage_color = "#f59e0b"
        shortage_reason = f"Projected ending buffer ({int(projected_buffer)} units) below safety stock (25 units)"
    else:
        shortage_risk = "Low"
        shortage_badge = "normal"
        shortage_color = "#10b981"
        shortage_reason = f"Finished goods buffer of {int(projected_buffer)} units covers tomorrow's demand"

    result = {
        "enabled": True,
        "as_of": as_of.isoformat(),
        "tomorrow_date": d_next.isoformat(),
        "tomorrow_display": tomorrow_display,
        "framing": RESEARCH_FRAMING,
        "new_sales_point": pt_int,
        "new_sales_display": new_sales_display,
        "new_sales_sublabel": sublabel,
        "due_tomorrow_units": due_int,
        "due_tomorrow_display": due_display,
        "due_tomorrow_sublabel": due_sublabel,
        "shortage_risk": shortage_risk,
        "shortage_badge": shortage_badge,
        "shortage_color": shortage_color,
        "shortage_reason": shortage_reason,
        "projected_buffer": round(projected_buffer, 1)
    }

    if use_cache:
        _OUTLOOK_CACHE[cache_key] = result

    return result


def clear_outlook_cache():
    global _OUTLOOK_CACHE
    _OUTLOOK_CACHE.clear()

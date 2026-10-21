"""
web/app.py — SAGE Phase F: Executive Read-Only Web Dashboard.

Stack:
- FastAPI + Jinja2 + Chart.js (v4.4.1 from cdnjs).
- Zero Node build, zero React.
- Token authentication: validated against SAGE_WEB_TOKEN via query param (?token=)
  or Authorization header (Bearer <token>).
- Responsive, executive aesthetic with Light / Dark mode support.
- Zero-Leakage: Ground truth is quarantined exclusively to web/research_view.py (/research).
"""

from __future__ import annotations

from datetime import date, datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from stage9.clock import get_as_of_date
from stage9.snapshot import compute_daily_snapshot, SNAPSHOTS_DIR
from stage9.priorities import compute_priorities
from stage9.narrate import generate_executive_narrative
from stage9.status import RESEARCH_FRAMING, get_packet_display_status
from stage9.render_email import load_evidence_packets, load_stage8_narratives
from stage9.scheduler import load_schedule_config, SENT_LOG_PATH
from web.research_view import load_research_evaluation_data

app = FastAPI(
    title="SAGE Operations & Causal Platform",
    description="Strategic Analytics for Guided Execution — Executive Delivery Layer",
    version="2.0.0"
)

TEMPLATES_DIR = ROOT_DIR / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def mask_email(email_str: str) -> str:
    """Masks email address for read-only executive view: user***@domain.com."""
    if "@" not in email_str:
        return email_str
    user, domain = email_str.split("@", 1)
    if len(user) <= 3:
        masked_user = user[0] + "***"
    else:
        masked_user = user[:3] + "***"
    return f"{masked_user}@{domain}"


def verify_token(
    request: Request,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
) -> str:
    """
    Validates token from ?token=<token> or Authorization: Bearer <token>.
    Raises HTTP 401 if unauthorized.
    """
    expected_token = os.getenv("SAGE_WEB_TOKEN", "sage_dev_token_2025")

    # Check query param
    if token and token == expected_token:
        return token

    # Check header
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected_token:
            return parts[1]

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Valid SAGE_WEB_TOKEN required via ?token= or Authorization: Bearer <token>"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Web HTML Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    as_of: Optional[str] = Query(None, alias="as-of"),
    auth_token: str = Depends(verify_token)
):
    current_as_of = get_as_of_date(override=as_of)
    snap = compute_daily_snapshot(current_as_of)
    pri = compute_priorities(current_as_of, snapshot=snap)
    narr = generate_executive_narrative(snap, pri)

    packets = load_evidence_packets()
    causal_exceptions = []
    for pid, p in sorted(packets.items()):
        tier = p.get("top_tier", "NOISE")
        drv = p["drivers"][0]["label"] if p.get("drivers") else "Driver"
        tgts = ", ".join(p.get("target_labels", [])[:2])
        status_lbl = get_packet_display_status(p)
        causal_exceptions.append({
            "packet_id": pid,
            "tier": tier,
            "driver": drv,
            "targets": tgts,
            "status_label": status_lbl
        })

    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": current_as_of.isoformat(),
            "snapshot": snap,
            "priorities": pri,
            "narrative": narr,
            "causal_exceptions": causal_exceptions,
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/digests", response_class=HTMLResponse)
def digests_archive(request: Request, auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    # Discover available snapshots in analytics/snapshots
    snapshots_list = []
    if SNAPSHOTS_DIR.exists():
        for f in sorted(SNAPSHOTS_DIR.glob("snapshot_*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as s_file:
                    snapshots_list.append(json.load(s_file))
            except Exception:
                continue

    chronological = list(reversed(snapshots_list))
    chart_dates = [s.get("as_of", "") for s in chronological]
    chart_shortfall = [s.get("kpis", {}).get("total_production_shortfall", 0) for s in chronological]
    chart_severity = [s.get("composite_severity_score", 0.0) for s in chronological]
    chart_stockouts = [s.get("kpis", {}).get("total_material_stockouts", 0) for s in chronological]

    return templates.TemplateResponse(
        "digests.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": as_of.isoformat(),
            "snapshots": snapshots_list,
            "chart_dates": chart_dates,
            "chart_shortfall": chart_shortfall,
            "chart_severity": chart_severity,
            "chart_stockouts": chart_stockouts,
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/digest/{date_str}", response_class=HTMLResponse)
def digest_detail(date_str: str, request: Request, auth_token: str = Depends(verify_token)):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (expected YYYY-MM-DD)")

    snap = compute_daily_snapshot(d)
    pri = compute_priorities(d, snapshot=snap)
    narr = generate_executive_narrative(snap, pri)

    return templates.TemplateResponse(
        "digest_detail.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": d.isoformat(),
            "digest_date": date_str,
            "snapshot": snap,
            "priorities": pri,
            "narrative": narr,
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/priorities", response_class=HTMLResponse)
def priorities_page(
    request: Request,
    as_of: Optional[str] = Query(None, alias="as-of"),
    auth_token: str = Depends(verify_token)
):
    current_as_of = get_as_of_date(override=as_of)
    snap = compute_daily_snapshot(current_as_of)
    pri = compute_priorities(current_as_of, snapshot=snap)

    return templates.TemplateResponse(
        "priorities.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": current_as_of.isoformat(),
            "priorities": pri,
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/causal", response_class=HTMLResponse)
def causal_overview(request: Request, auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    packets = load_evidence_packets()
    packet_rows = []
    for pid, p in sorted(packets.items()):
        drv_lbl = p["drivers"][0]["label"] if p.get("drivers") else "Driver"
        m1 = f"{p['drivers'][0]['m1_score']:.4f}" if p.get("drivers") else "0.0000"
        m2 = f"{p['drivers'][0]['m2_score']:.4f}" if p.get("drivers") else "0.0000"
        packet_rows.append({
            "packet_id": pid,
            "targets": ", ".join(p.get("target_labels", [])[:2]),
            "driver": drv_lbl,
            "m1_score": m1,
            "m2_score": m2,
            "tier": p.get("top_tier", "NOISE"),
            "status_label": get_packet_display_status(p)
        })

    return templates.TemplateResponse(
        "causal.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": as_of.isoformat(),
            "packets": packet_rows,
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/causal/{packet_id}", response_class=HTMLResponse)
def causal_detail(packet_id: str, request: Request, auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    packets = load_evidence_packets()
    if packet_id not in packets:
        raise HTTPException(status_code=404, detail=f"Evidence packet {packet_id} not found")

    pkt = packets[packet_id]
    narratives = load_stage8_narratives()
    narr = narratives.get(packet_id, "No narrative available.")

    driver_labels = [d["label"][:30] for d in pkt.get("drivers", [])]
    m1_scores = [d["m1_score"] for d in pkt.get("drivers", [])]
    m2_scores = [d["m2_score"] for d in pkt.get("drivers", [])]

    return templates.TemplateResponse(
        "causal_detail.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": as_of.isoformat(),
            "packet": pkt,
            "target_labels_str": ", ".join(pkt.get("target_labels", [])),
            "narrative": narr,
            "driver_labels": driver_labels,
            "m1_scores": m1_scores,
            "m2_scores": m2_scores,
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/research", response_class=HTMLResponse)
def research_evaluation(request: Request, auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    research_data = load_research_evaluation_data()

    return templates.TemplateResponse(
        "research.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": as_of.isoformat(),
            "research_data": research_data,
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/method", response_class=HTMLResponse)
def method_page(request: Request, auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    return templates.TemplateResponse(
        "method.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": as_of.isoformat(),
            "framing": RESEARCH_FRAMING
        }
    )


@app.get("/schedule", response_class=HTMLResponse)
def schedule_page(request: Request, auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    cfg = load_schedule_config()

    masked_recipients = {
        job: [mask_email(e) for e in emails]
        for job, emails in cfg.get("recipients", {}).items()
    }

    sent_logs = []
    if SENT_LOG_PATH.exists():
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        sent_logs.append(json.loads(line.strip()))
                    except Exception:
                        continue
    sent_logs = list(reversed(sent_logs))[:20]

    return templates.TemplateResponse(
        "schedule.html",
        {
            "request": request,
            "token": auth_token,
            "as_of": as_of.isoformat(),
            "schedule_info": {
                "timezone": cfg.get("timezone", "Asia/Kolkata"),
                "jobs": cfg.get("jobs", {}),
                "masked_recipients": masked_recipients
            },
            "sent_logs": sent_logs,
            "framing": RESEARCH_FRAMING
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# JSON API Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/snapshot")
def api_snapshot(auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    return compute_daily_snapshot(as_of)


@app.get("/api/priorities")
def api_priorities(auth_token: str = Depends(verify_token)):
    as_of = get_as_of_date()
    return compute_priorities(as_of)


@app.get("/api/causal")
def api_causal(auth_token: str = Depends(verify_token)):
    return load_evidence_packets()


@app.get("/api/causal/{packet_id}")
def api_causal_packet(packet_id: str, auth_token: str = Depends(verify_token)):
    packets = load_evidence_packets()
    if packet_id not in packets:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")
    return packets[packet_id]


@app.get("/api/research")
def api_research(auth_token: str = Depends(verify_token)):
    return load_research_evaluation_data()

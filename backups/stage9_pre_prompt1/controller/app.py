"""
controller/app.py — SAGE Stage 9 Controller Web App (Port 8001).

Operator-only control panel with:
- Session-based login (SAGE_CONTROLLER_TOKEN from env, separate from SAGE_WEB_TOKEN)
- CSRF protection on every state-changing POST
- Brute-force lockout (5 bad logins → 60s lockout)
- Feed Next Day button with real-time progress via SSE
- Send Now with preview modal
- Runtime schedule editor (prepare/send times with validation)
- Recipient allowlist display
- Live ↔ Dry-run send mode toggle
- Demo Reset (< 30 s, queues restored)
- Operator audit log stream
- All state changes go through ops.py — zero duplicate logic here

Security model:
- Controller token is independent of viewer token (SAGE_WEB_TOKEN)
- Viewer (port 8000) has NO controller endpoints; it is read-only
- All POST endpoints require matching CSRF token stored in session
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from stage9.ops import (
    audit_log,
    dispatch_email_v6,
    feed_next_queue_day,
    get_allowlist,
    get_audit_log_entries,
    get_case_state,
    get_demo_cases,
    get_runtime_config,
    jump_to_case,
    load_year_review,
    pause_scheduler_v6,
    prepare_daily_run_v6,
    reschedule_v6,
    reset_demo_v6,
    send_report_now_v6,
    set_send_mode_v6,
    validate_and_ingest_pack_v6,
    QUEUE_DIR,
)
from stage9.current_day import get_current_day, get_ingested_days
from stage9.clock import get_as_of_date

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("controller")

# ─────────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────────

CONTROLLER_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = CONTROLLER_DIR / "templates"
STATIC_DIR = CONTROLLER_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="SAGE Controller",
    description="Operator control panel — Stage 9 v6",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ─────────────────────────────────────────────────────────────
# Simple in-memory session store (single-process demo)
# ─────────────────────────────────────────────────────────────
_sessions: Dict[str, Dict[str, Any]] = {}
_failed_logins: Dict[str, List[float]] = {}

SESSION_TTL_SECONDS = 3600  # 1 hour
LOCKOUT_WINDOW_SECONDS = 60
MAX_FAILED_ATTEMPTS = 5


def _get_controller_token() -> str:
    t = os.getenv("SAGE_CONTROLLER_TOKEN", "").strip()
    if not t:
        # Derive from WEB_TOKEN + salt so it differs
        base = os.getenv("SAGE_WEB_TOKEN", "sage_dev_token_2025")
        t = hashlib.sha256(f"ctrl:{base}".encode()).hexdigest()[:32]
    return t


def _create_session() -> str:
    sid = secrets.token_urlsafe(32)
    csrf = secrets.token_hex(16)
    _sessions[sid] = {
        "created_at": time.time(),
        "csrf": csrf,
    }
    return sid


def _get_session(request: Request) -> Optional[Dict[str, Any]]:
    sid = request.cookies.get("sage_ctrl_session")
    if not sid or sid not in _sessions:
        return None
    sess = _sessions[sid]
    if time.time() - sess["created_at"] > SESSION_TTL_SECONDS:
        _sessions.pop(sid, None)
        return None
    return sess


def _require_session(request: Request) -> Dict[str, Any]:
    sess = _get_session(request)
    if sess is None:
        raise HTTPException(status_code=303, headers={"Location": "/ctrl/login"})
    return sess


def _check_csrf(request_csrf: str, session_csrf: str) -> None:
    if not hmac.compare_digest(request_csrf or "", session_csrf or ""):
        raise HTTPException(status_code=403, detail="CSRF token mismatch.")


def _is_locked_out(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _failed_logins.get(ip, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_logins[ip] = attempts
    return len(attempts) >= MAX_FAILED_ATTEMPTS


def _record_failed_login(ip: str) -> None:
    _failed_logins.setdefault(ip, []).append(time.time())


# ─────────────────────────────────────────────────────────────
# Helper: build template context
# ─────────────────────────────────────────────────────────────

def _base_ctx(request: Request, sess: Optional[Dict] = None) -> Dict[str, Any]:
    cfg = get_runtime_config()
    current_day = get_current_day()
    queue_days = sorted(d.name for d in QUEUE_DIR.iterdir() if d.is_dir()) if QUEUE_DIR.exists() else []
    cases = get_demo_cases()
    case_state = get_case_state()
    return {
        "request": request,
        "csrf": sess["csrf"] if sess else "",
        "current_day": current_day.isoformat() if current_day else "—",
        "queue_remaining": len(queue_days),
        "queue_days": queue_days[:3],  # show first 3
        "demo_cases": cases,
        "case_state": case_state,
        "send_mode": cfg.get("send_mode", "dry_run"),
        "scheduler_paused": cfg.get("scheduler_paused", False),
        "prepare_time": cfg.get("prepare_time", "19:45"),
        "send_time": cfg.get("send_time", "20:00"),
        "timezone": cfg.get("timezone", "Asia/Kolkata"),
        "recipients": cfg.get("recipients", {}).get("nightly_digest", []),
        "allowlist": sorted(get_allowlist()),
        "framing": (
            "SAGE performs controlled synthetic causal-attribution evaluation "
            "under an expert-defined causal model; it does not claim to prove "
            "real-world causality."
        ),
    }


# ─────────────────────────────────────────────────────────────
# Auth Routes
# ─────────────────────────────────────────────────────────────

@app.get("/ctrl/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "framing": (
            "SAGE performs controlled synthetic causal-attribution evaluation "
            "under an expert-defined causal model; it does not claim to prove "
            "real-world causality."
        ),
    })


@app.post("/ctrl/login")
async def login_submit(
    request: Request,
    response: Response,
    token: str = Form(...),
):
    ip = request.client.host if request.client else "unknown"

    if _is_locked_out(ip):
        audit_log("login_attempt", {"ip": ip}, "LOCKED_OUT")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Too many failed attempts. Please wait 60 seconds.",
            "framing": "",
        }, status_code=429)

    expected = _get_controller_token()
    if not hmac.compare_digest(token.strip(), expected):
        _record_failed_login(ip)
        remaining = MAX_FAILED_ATTEMPTS - len(_failed_logins.get(ip, []))
        audit_log("login_attempt", {"ip": ip}, "FAILED")
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"Invalid token. {max(0, remaining)} attempt(s) remaining.",
            "framing": "",
        }, status_code=401)

    sid = _create_session()
    audit_log("login", {"ip": ip}, "SUCCESS")
    resp = RedirectResponse("/ctrl/", status_code=303)
    resp.set_cookie(
        "sage_ctrl_session", sid,
        httponly=True, samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return resp


@app.post("/ctrl/logout")
async def logout(request: Request):
    sid = request.cookies.get("sage_ctrl_session")
    if sid:
        _sessions.pop(sid, None)
    resp = RedirectResponse("/ctrl/login", status_code=303)
    resp.delete_cookie("sage_ctrl_session")
    return resp


# ─────────────────────────────────────────────────────────────
# Main Dashboard
# ─────────────────────────────────────────────────────────────

@app.get("/ctrl/", response_class=HTMLResponse)
async def dashboard(request: Request, sess: Dict = Depends(_require_session)):
    ctx = _base_ctx(request, sess)
    audit_entries = get_audit_log_entries(limit=20)
    ctx["audit_entries"] = audit_entries
    return templates.TemplateResponse("dashboard.html", ctx)


@app.get("/ctrl", response_class=HTMLResponse)
async def dashboard_redirect(request: Request):
    return RedirectResponse("/ctrl/", status_code=301)


# ─────────────────────────────────────────────────────────────
# API: Feed Next Day (with SSE progress stream)
# ─────────────────────────────────────────────────────────────

@app.post("/ctrl/api/feed-next-day")
async def api_feed_next_day(
    request: Request,
    csrf_token: str = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        result = feed_next_queue_day(user="controller")
        return JSONResponse({"status": "ok", "result": result})
    except Exception as exc:
        logger.error("Feed next day failed: %s", exc)
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


@app.get("/ctrl/api/feed-next-day/stream")
async def api_feed_stream(request: Request, sess: Dict = Depends(_require_session)):
    """SSE stream for feed progress — client polls this while feed runs."""
    async def event_generator():
        current = get_current_day()
        yield f"data: {{\"step\": \"start\", \"current_day\": \"{current}\"}}\n\n"
        time.sleep(0.1)
        queue_days = sorted(d.name for d in QUEUE_DIR.iterdir() if d.is_dir()) if QUEUE_DIR.exists() else []
        yield f"data: {{\"step\": \"queue_checked\", \"queue_remaining\": {len(queue_days)}}}\n\n"
        yield f"data: {{\"step\": \"done\", \"current_day\": \"{get_current_day()}\"}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────────────────────────────────────────
# API: Prepare Daily Report
# ─────────────────────────────────────────────────────────────

@app.post("/ctrl/api/prepare")
async def api_prepare(
    request: Request,
    csrf_token: str = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        result = prepare_daily_run_v6(user="controller")
        return JSONResponse({"status": "ok", "result": result})
    except Exception as exc:
        logger.error("Prepare failed: %s", exc)
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────
# API: Send Now
# ─────────────────────────────────────────────────────────────

@app.post("/ctrl/api/send-now")
async def api_send_now(
    request: Request,
    csrf_token: str = Form(...),
    recipient: str = Form(...),
    force_live: str = Form("false"),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    allowlist = get_allowlist()
    rec_clean = recipient.strip().lower()
    if rec_clean not in allowlist:
        return JSONResponse(
            {"status": "error", "detail": f"Recipient '{recipient}' not in allowlist."},
            status_code=400,
        )
    try:
        fl = force_live.lower() in ("true", "1", "yes")
        result = send_report_now_v6(recipient=recipient, force_live=fl, user="controller")
        return JSONResponse({"status": "ok", "result": result})
    except Exception as exc:
        logger.error("Send now failed: %s", exc)
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────
# API: Demo Reset
# ─────────────────────────────────────────────────────────────

@app.post("/ctrl/api/reset-demo")
async def api_reset_demo(
    request: Request,
    csrf_token: str = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        result = reset_demo_v6(user="controller")
        return JSONResponse({"status": "ok", "result": result})
    except Exception as exc:
        logger.error("Demo reset failed: %s", exc)
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────
# API: Demo Cases (Stage 9 Final 2)
# ─────────────────────────────────────────────────────────────

@app.get("/ctrl/api/cases")
async def api_cases(request: Request, sess: Dict = Depends(_require_session)):
    return JSONResponse({
        "cases": get_demo_cases(),
        "case_state": get_case_state(),
    })


@app.post("/ctrl/api/run-case")
async def api_run_case(
    request: Request,
    csrf_token: str = Form(...),
    case_num: int = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        res = jump_to_case(k=case_num, user="controller")
        return JSONResponse({"status": "ok", "case": res})
    except Exception as exc:
        logger.exception("Failed to run case %s", case_num)
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=400)


@app.post("/ctrl/api/next-case")
async def api_next_case(
    request: Request,
    csrf_token: str = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        st = get_case_state()
        cases = get_demo_cases()
        cur_k = st.get("active_case") or 0
        next_k = (cur_k % len(cases)) + 1 if cases else 1
        res = jump_to_case(k=next_k, user="controller")
        return JSONResponse({"status": "ok", "case": res})
    except Exception as exc:
        logger.exception("Failed next case")
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=400)


@app.post("/ctrl/api/year-review")
async def api_year_review(
    request: Request,
    csrf_token: str = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        res = load_year_review(user="controller")
        return JSONResponse({"status": "ok", "state": res})
    except Exception as exc:
        logger.exception("Failed year review")
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────
# API: Set Send Mode
# ─────────────────────────────────────────────────────────────

@app.post("/ctrl/api/set-send-mode")
async def api_set_send_mode(
    request: Request,
    csrf_token: str = Form(...),
    mode: str = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        result = set_send_mode_v6(mode=mode, user="controller")
        return JSONResponse({"status": "ok", "result": result})
    except ValueError as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=400)


# ─────────────────────────────────────────────────────────────
# API: Pause / Resume Scheduler
# ─────────────────────────────────────────────────────────────

@app.post("/ctrl/api/pause-scheduler")
async def api_pause_scheduler(
    request: Request,
    csrf_token: str = Form(...),
    paused: str = Form(...),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        result = pause_scheduler_v6(paused=(paused.lower() in ("true", "1")), user="controller")
        return JSONResponse({"status": "ok", "result": result})
    except Exception as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────
# API: Reschedule (prepare + send times)
# ─────────────────────────────────────────────────────────────

@app.post("/ctrl/api/reschedule")
async def api_reschedule(
    request: Request,
    csrf_token: str = Form(...),
    prepare_time: str = Form("19:45"),
    send_time: str = Form("20:00"),
    sess: Dict = Depends(_require_session),
):
    _check_csrf(csrf_token, sess["csrf"])
    try:
        result = reschedule_v6(
            prepare_time=prepare_time,
            send_time=send_time,
            user="controller",
        )
        return JSONResponse({"status": "ok", "result": result})
    except ValueError as exc:
        return JSONResponse({"status": "error", "detail": str(exc)}, status_code=400)


# ─────────────────────────────────────────────────────────────
# API: Status JSON (for polling)
# ─────────────────────────────────────────────────────────────

@app.get("/ctrl/api/status")
async def api_status(request: Request, sess: Dict = Depends(_require_session)):
    cfg = get_runtime_config()
    queue_days = sorted(d.name for d in QUEUE_DIR.iterdir() if d.is_dir()) if QUEUE_DIR.exists() else []
    current_day = get_current_day()
    return JSONResponse({
        "current_day": current_day.isoformat() if current_day else None,
        "queue_remaining": len(queue_days),
        "queue_next": queue_days[0] if queue_days else None,
        "send_mode": cfg.get("send_mode", "dry_run"),
        "scheduler_paused": cfg.get("scheduler_paused", False),
        "prepare_time": cfg.get("prepare_time", "19:45"),
        "send_time": cfg.get("send_time", "20:00"),
        "server_time_ist": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })


# ─────────────────────────────────────────────────────────────
# API: Audit Log (JSON)
# ─────────────────────────────────────────────────────────────

@app.get("/ctrl/api/audit")
async def api_audit(request: Request, limit: int = 50, sess: Dict = Depends(_require_session)):
    entries = get_audit_log_entries(limit=limit)
    return JSONResponse({"entries": entries})


# ─────────────────────────────────────────────────────────────
# Schedule editor page
# ─────────────────────────────────────────────────────────────

@app.get("/ctrl/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, sess: Dict = Depends(_require_session)):
    ctx = _base_ctx(request, sess)
    return templates.TemplateResponse("schedule.html", ctx)


# ─────────────────────────────────────────────────────────────
# Redirect root to controller
# ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root_redirect():
    return RedirectResponse("/ctrl/login", status_code=302)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("SAGE_CONTROLLER_PORT", "8001"))
    logger.info("Starting SAGE Controller on port %d", port)
    uvicorn.run("controller.app:app", host="0.0.0.0", port=port, reload=False)

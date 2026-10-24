#!/usr/bin/env bash
# run_sage.sh — Start SAGE Executive Viewer and Operator Controller
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Stop stale SAGE processes if running
if [ -f "$DIR/stop_sage.sh" ]; then
    bash "$DIR/stop_sage.sh" > /dev/null 2>&1 || true
fi

# Double-check ports 8000 and 8001; if any lingering process exists, kill it
for port in 8000 8001; do
    PIDS=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        for p in $PIDS; do
            kill -9 "$p" 2>/dev/null || true
        done
    fi
done

# 2. Activate venv
if [ -f "$DIR/venv/bin/activate" ]; then
    source "$DIR/venv/bin/activate"
fi

# 3. Load .env safely
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

# 4. Prepare logs directory
mkdir -p "$DIR/logs"

# Print Git commit hash and start time
GIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Starting SAGE Platform [Commit: $GIT_HASH, Start: $START_TIME]"

# 5. Reset send mode to Dry-run unconditionally on start
"$DIR/venv/bin/python" -c "from stage9.ops import set_send_mode_v6; set_send_mode_v6('dry_run', user='run_sage')" > /dev/null 2>&1 || true

# 6. Start Viewer (127.0.0.1:8000)
PYTHONPATH="$DIR" "$DIR/venv/bin/uvicorn" web.app:app --host 127.0.0.1 --port 8000 > "$DIR/logs/viewer.log" 2>&1 &
VIEWER_PID=$!
echo "$VIEWER_PID" > "$DIR/logs/viewer.pid"

# 7. Start Controller (127.0.0.1:8001)
PYTHONPATH="$DIR" "$DIR/venv/bin/uvicorn" controller.app:app --host 127.0.0.1 --port 8001 > "$DIR/logs/controller.log" 2>&1 &
CTRL_PID=$!
echo "$CTRL_PID" > "$DIR/logs/controller.pid"
echo "$VIEWER_PID $CTRL_PID" > "$DIR/.sage.pid"

# 8. Prevent system sleep while SAGE is running (macOS caffeinate)
if [ "$(uname -s)" = "Darwin" ] && command -v caffeinate >/dev/null 2>&1; then
    caffeinate -i -w "$VIEWER_PID" >/dev/null 2>&1 &
    echo $! > "$DIR/logs/caffeinate.pid"
fi

# 9. Health check: Wait up to 20 seconds for both servers to respond with HTTP 200 on /health
echo "Waiting for health checks on 127.0.0.1:8000/health and 127.0.0.1:8001/health..."
READY=0
for i in {1..40}; do
    STATUS_8000=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo "000")
    STATUS_8001=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/health 2>/dev/null || echo "000")
    if [ "$STATUS_8000" = "200" ] && [ "$STATUS_8001" = "200" ]; then
        READY=1
        break
    fi
    sleep 0.5
done

if [ "$READY" -ne 1 ]; then
    echo "ERROR: Server health check failed! Viewer status: $STATUS_8000, Controller status: $STATUS_8001."
    echo "Check logs/viewer.log and logs/controller.log for details."
    bash "$DIR/stop_sage.sh" > /dev/null 2>&1 || true
    exit 1
fi

NEXT_RUNS=$("$DIR/venv/bin/python" -c "
from datetime import datetime, timedelta
import pytz
tz = pytz.timezone('Asia/Kolkata')
now = datetime.now(tz)
p_today = now.replace(hour=19, minute=45, second=0, microsecond=0)
s_today = now.replace(hour=20, minute=0, second=0, microsecond=0)
next_p = p_today if now < p_today else p_today + timedelta(days=1)
next_s = s_today if now < s_today else s_today + timedelta(days=1)
print(f'Next Prepare : {next_p.strftime(\"%Y-%m-%d %H:%M:%S\")} IST (19:45)')
print(f'Next Send    : {next_s.strftime(\"%Y-%m-%d %H:%M:%S\")} IST (20:00)')
")

echo "=================================================================="
echo "SAGE Operations Platform is RUNNING (Verified Healthy)"
echo "Git Commit Served : $GIT_HASH"
echo "Started At        : $START_TIME"
echo "$NEXT_RUNS"
echo "=================================================================="
echo "Executive Dashboard (Viewer) : http://127.0.0.1:8000/"
echo "  -> Sign in using SAGE_WEB_TOKEN from .env"
echo "Operator Control Panel       : http://127.0.0.1:8001/ctrl/"
echo "  -> Sign in using SAGE_CONTROLLER_TOKEN from .env"
echo "=================================================================="
echo "Viewer PID     : $VIEWER_PID (logs: logs/viewer.log)"
echo "Controller PID : $CTRL_PID (logs: logs/controller.log)"
echo "Mode           : DRY-RUN (Default on start; reset on every restart)"
echo "To stop cleanly: ./stop_sage.sh"
echo "=================================================================="

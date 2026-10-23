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

# 5. Start Viewer (127.0.0.1:8000)
PYTHONPATH="$DIR" "$DIR/venv/bin/uvicorn" web.app:app --host 127.0.0.1 --port 8000 > "$DIR/logs/viewer.log" 2>&1 &
VIEWER_PID=$!
echo "$VIEWER_PID" > "$DIR/logs/viewer.pid"

# 6. Start Controller (127.0.0.1:8001)
PYTHONPATH="$DIR" "$DIR/venv/bin/uvicorn" controller.app:app --host 127.0.0.1 --port 8001 > "$DIR/logs/controller.log" 2>&1 &
CTRL_PID=$!
echo "$CTRL_PID" > "$DIR/logs/controller.pid"
echo "$VIEWER_PID $CTRL_PID" > "$DIR/.sage.pid"

# 7. Health check: Wait up to 10 seconds for both servers to respond with HTTP 200 on /health
echo "Waiting for health checks on 127.0.0.1:8000/health and 127.0.0.1:8001/health..."
READY=0
for i in {1..20}; do
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

WEB_TOKEN="${SAGE_WEB_TOKEN:-sage_dev_token_2025}"

echo "=================================================================="
echo "SAGE Operations Platform is RUNNING (Verified Healthy)"
echo "Git Commit Served : $GIT_HASH"
echo "Started At        : $START_TIME"
echo "=================================================================="
echo "Executive Dashboard (Viewer) : http://127.0.0.1:8000/?token=$WEB_TOKEN"
echo "Operator Control Panel       : http://127.0.0.1:8001/ctrl/"
echo "=================================================================="
echo "Viewer PID     : $VIEWER_PID (logs: logs/viewer.log)"
echo "Controller PID : $CTRL_PID (logs: logs/controller.log)"
echo "Mode           : DRY-RUN (Default on start)"
echo "To stop cleanly: ./stop_sage.sh"
echo "=================================================================="

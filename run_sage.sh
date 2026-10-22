#!/usr/bin/env bash
# run_sage.sh — Start SAGE Executive Viewer and Operator Controller
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Activate venv
if [ -f "$DIR/venv/bin/activate" ]; then
    source "$DIR/venv/bin/activate"
fi

# 2. Load .env safely
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

# 3. Check if ports 8000 or 8001 are already in use
PID_8000=$(lsof -ti :8000 || true)
if [ -n "$PID_8000" ]; then
    echo "ERROR: Port 8000 is already in use by process PID $PID_8000."
    echo "Run './stop_sage.sh' or kill PID $PID_8000 before starting SAGE."
    exit 1
fi

PID_8001=$(lsof -ti :8001 || true)
if [ -n "$PID_8001" ]; then
    echo "ERROR: Port 8001 is already in use by process PID $PID_8001."
    echo "Run './stop_sage.sh' or kill PID $PID_8001 before starting SAGE."
    exit 1
fi

# 4. Prepare logs directory
mkdir -p "$DIR/logs"

# 5. Start Viewer (127.0.0.1:8000)
PYTHONPATH="$DIR" "$DIR/venv/bin/uvicorn" web.app:app --host 127.0.0.1 --port 8000 > "$DIR/logs/viewer.log" 2>&1 &
VIEWER_PID=$!
echo "$VIEWER_PID" > "$DIR/logs/viewer.pid"

# 6. Start Controller (127.0.0.1:8001)
PYTHONPATH="$DIR" "$DIR/venv/bin/uvicorn" controller.app:app --host 127.0.0.1 --port 8001 > "$DIR/logs/controller.log" 2>&1 &
CTRL_PID=$!
echo "$CTRL_PID" > "$DIR/logs/controller.pid"
echo "$VIEWER_PID $CTRL_PID" > "$DIR/.sage.pid"

# Sleep briefly to ensure startup
sleep 1.5

# 7. Print URLs
echo "=================================================================="
echo "SAGE Operations & Causal Evaluation Platform is running!"
echo "=================================================================="
echo "Executive Dashboard (Viewer) : http://127.0.0.1:8000/?token=sage_dev_token_2025"
echo "Operator Control Panel       : http://127.0.0.1:8001/ctrl/"
echo "=================================================================="
echo "Viewer PID     : $VIEWER_PID (logs: logs/viewer.log)"
echo "Controller PID : $CTRL_PID (logs: logs/controller.log)"
echo "PID file       : .sage.pid"
echo "To stop both cleanly, run    : ./stop_sage.sh"
echo "=================================================================="

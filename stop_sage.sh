#!/usr/bin/env bash
# stop_sage.sh — Stop SAGE Executive Viewer and Operator Controller cleanly
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Stopping SAGE servers..."

# Stop by PID files if present
for pidfile in "$DIR/logs/viewer.pid" "$DIR/logs/controller.pid" "$DIR/.sage.pid"; do
    if [ -f "$pidfile" ]; then
        PIDS=$(cat "$pidfile" || true)
        for PID in $PIDS; do
            if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                kill "$PID" 2>/dev/null || true
                echo "Stopped process $PID ($pidfile)"
            fi
        done
        rm -f "$pidfile"
    fi
done

# Also ensure any lingering process on 8000 or 8001 is stopped
for port in 8000 8001; do
    PIDS=$(lsof -ti :$port || true)
    if [ -n "$PIDS" ]; then
        for p in $PIDS; do
            kill "$p" 2>/dev/null || true
            echo "Stopped process $p on port $port"
        done
    fi
done

sleep 0.5
echo "SAGE servers stopped successfully."

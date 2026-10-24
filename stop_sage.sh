#!/usr/bin/env bash
# stop_sage.sh — Stop SAGE Executive Viewer and Operator Controller cleanly
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Stopping SAGE servers..."

# Stop by PID files if present
for pidfile in "$DIR/logs/viewer.pid" "$DIR/logs/controller.pid" "$DIR/logs/caffeinate.pid" "$DIR/.sage.pid"; do
    if [ -f "$pidfile" ]; then
        PIDS=$(cat "$pidfile" 2>/dev/null || true)
        for PID in $PIDS; do
            if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                kill "$PID" 2>/dev/null || true
            fi
        done
        rm -f "$pidfile"
    fi
done

# Ensure all processes listening on 8000 and 8001 are stopped
for port in 8000 8001; do
    PIDS=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        for p in $PIDS; do
            kill "$p" 2>/dev/null || true
        done
    fi
done

sleep 0.5

# Force kill any lingering leftovers
for port in 8000 8001; do
    PIDS=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        for p in $PIDS; do
            kill -9 "$p" 2>/dev/null || true
        done
    fi
done

# Verify ports are completely free
REMAINING=$(lsof -nP -i :8000 -i :8001 2>/dev/null || true)
if [ -n "$REMAINING" ]; then
    echo "WARNING: Lingering listeners detected on ports 8000/8001:"
    echo "$REMAINING"
    exit 1
fi

echo "SAGE servers stopped successfully. Ports 8000 and 8001 are FREE."

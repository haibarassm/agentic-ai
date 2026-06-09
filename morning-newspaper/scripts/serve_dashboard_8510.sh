#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/runtime"

if [ ! -d "$RUNTIME_DIR" ]; then
    echo "runtime dir not found: $RUNTIME_DIR" >&2
    exit 1
fi

pkill -f "python3 -m http.server 8510" || true
cd "$RUNTIME_DIR"
nohup python3 -m http.server 8510 --bind 0.0.0.0 >/tmp/morning-newspaper-8510.log 2>&1 &
echo $! > /tmp/morning-newspaper-8510.pid
echo "started 8510 server pid=$(cat /tmp/morning-newspaper-8510.pid) serving $RUNTIME_DIR"

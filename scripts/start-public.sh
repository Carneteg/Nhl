#!/bin/sh
set -eu

DB="${NHLGM_DB:-/var/lib/nhlgm/nhl_gm.sqlite3}"
PORT="${PORT:-8000}"
mkdir -p "$(dirname "$DB")"

if [ ! -s "$DB" ]; then
  # Render requires a listener on its injected PORT while the first import runs.
  # Keep /health available, then atomically hand the port to the real app.
  python -m nhlgm.readiness --host 0.0.0.0 --port "$PORT" &
  READY_PID=$!
  trap 'kill "$READY_PID" 2>/dev/null || true' EXIT INT TERM
  echo "No database found at $DB; importing the NHL 2025-26 baseline."
  python -m nhlgm --db "$DB" bootstrap:2025 --team ALL --season 20252026
  python -m nhlgm --db "$DB" simulation:new --team EDM --date 2025-07-01
  kill "$READY_PID" 2>/dev/null || true
  wait "$READY_PID" 2>/dev/null || true
  trap - EXIT INT TERM
fi

echo "Starting NHL GM on 0.0.0.0:$PORT"
exec python -m nhlgm --db "$DB" web --host 0.0.0.0 --port "$PORT"

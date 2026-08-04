#!/bin/sh
set -eu

DB="${NHLGM_DB:-/var/lib/nhlgm/nhl_gm.sqlite3}"
PORT="${PORT:-8000}"
BASELINE_VERSION="2025-26-contracts-v3"
BASELINE_MARKER="$DB.baseline-version"
mkdir -p "$(dirname "$DB")"

CURRENT_BASELINE="$(cat "$BASELINE_MARKER" 2>/dev/null || true)"
if [ ! -s "$DB" ] || [ "$CURRENT_BASELINE" != "$BASELINE_VERSION" ]; then
  # Render requires a listener on its injected PORT while the first import runs.
  # Keep /health available, then atomically hand the port to the real app.
  python -m nhlgm.readiness --host 0.0.0.0 --port "$PORT" &
  READY_PID=$!
  trap 'kill "$READY_PID" 2>/dev/null || true' EXIT INT TERM
  echo "Importing verified NHL baseline $BASELINE_VERSION into $DB."
  python -m nhlgm --db "$DB" bootstrap:2025 --team ALL --season 20252026
  python -m nhlgm --db "$DB" simulation:new --team EDM --date 2025-07-01
  printf '%s\n' "$BASELINE_VERSION" > "$BASELINE_MARKER"
  kill "$READY_PID" 2>/dev/null || true
  wait "$READY_PID" 2>/dev/null || true
  trap - EXIT INT TERM
fi

echo "Starting NHL GM on 0.0.0.0:$PORT"
exec python -m nhlgm --db "$DB" web --host 0.0.0.0 --port "$PORT"

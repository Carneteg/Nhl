#!/bin/sh
set -eu

DB="${NHLGM_DB:-/var/lib/nhlgm/nhl_gm.sqlite3}"
PORT="${PORT:-8000}"
mkdir -p "$(dirname "$DB")"

if [ ! -s "$DB" ]; then
  echo "No database found at $DB; importing the NHL 2025-26 baseline."
  python -m nhlgm --db "$DB" bootstrap:2025 --team ALL --season 20252026
  python -m nhlgm --db "$DB" simulation:new --team EDM --date 2025-07-01
fi

exec python -m nhlgm --db "$DB" web --host 0.0.0.0 --port "$PORT"


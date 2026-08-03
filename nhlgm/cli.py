from __future__ import annotations

import argparse
import json
import os

from .bootstrap import load_fixtures
from .db import DEFAULT_DB, connect, migrate
from .exporter import export
from .services import advance, audits, new_simulation
from .sync import NHL_TEAMS, sync_league, sync_team_roster
from .web import serve


def add_sync_options(parser):
    parser.add_argument("--team", default="ALL", help="NHL abbreviation or ALL")
    parser.add_argument("--season", default="20252026")
    parser.add_argument("--date", default="2025-07-01")
    parser.add_argument("--source", default="nhl,capwages")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--skip-contracts", action="store_true")


def parser():
    root = argparse.ArgumentParser(prog="nhl-gm")
    root.add_argument("--db", default=str(DEFAULT_DB))
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("bootstrap:2025", "sync:nhl", "sync:contracts", "sync:all"):
        add_sync_options(sub.add_parser(name))
    for name in ("sync:ahl", "sync:draft-picks", "sync:prospects"):
        add_sync_options(sub.add_parser(name))
    draft = sub.add_parser("sync:draft-class")
    draft.add_argument("--year", type=int, required=True)
    draft.add_argument("--dry-run", action="store_true")
    simulation = sub.add_parser("simulation:new")
    simulation.add_argument("--team", default="EDM")
    simulation.add_argument("--date", default="2025-07-01")
    sub.add_parser("simulation:advance")
    for name in ("audit:rosters", "audit:contracts", "audit:cap", "audit:draft"):
        sub.add_parser(name)
    workbook = sub.add_parser("export:franchise")
    workbook.add_argument("--output", default="exports/Edmonton_Oilers_GM_Simulation_2025_26_v2.0.xlsx")
    web = sub.add_parser("web")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "web":
        return serve(args.host, args.port, args.db)
    with connect(args.db) as db:
        migrate(db)
        if args.command in {"bootstrap:2025", "sync:nhl", "sync:contracts", "sync:all"}:
            load_fixtures(db)
            teams = NHL_TEAMS if args.team == "ALL" else (args.team.upper(),)
            result = sync_league(db, args.season, teams, args.dry_run, args.force,
                                 not args.skip_contracts, reset=args.command in {"bootstrap:2025", "sync:all"})
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if args.command in {"sync:ahl", "sync:draft-picks", "sync:prospects", "sync:draft-class"}:
            load_fixtures(db)
            print(json.dumps({"status": "fixture-only", "command": args.command, "dry_run": args.dry_run}))
            return
        if args.command == "simulation:new":
            print(json.dumps({"simulation_id": new_simulation(db, args.team, args.date), "start_date": args.date}))
            return
        if args.command == "simulation:advance":
            print(json.dumps({"simulation_date": advance(db)}))
            return
        if args.command.startswith("audit:"):
            print(json.dumps(audits(db), ensure_ascii=False, indent=2))
            return
        if args.command == "export:franchise":
            print(json.dumps({"export": str(export(db, args.output))}))


if __name__ == "__main__":
    main()

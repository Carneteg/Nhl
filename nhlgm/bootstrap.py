from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from .db import stable_player_id,json_dump
from .sync import source_record

ROOT=Path(__file__).resolve().parents[1]
def load_fixtures(db):
    data=json.loads((ROOT/"fixtures"/"baseline.json").read_text())
    db.executemany("INSERT OR IGNORE INTO teams(id,league,name,abbreviation,conference,division) VALUES(?,?,?,?,?,?)",[(t["abbr"],"NHL",t["name"],t["abbr"],t.get("conference"),t.get("division")) for t in data["teams"]])
    personalities=["Aggressiv contender","Försiktig konservativ","Analytics-driven","Old-school scout","Rebuild specialist","Cap disciplinarian","Draft-and-develop","Patient developer"]
    for i,t in enumerate(data["teams"]): db.execute("INSERT OR IGNORE INTO gm_profiles(team_id,name,personality,risk_tolerance,analytics,competitive_window) VALUES(?,?,?,?,?,?)",(t["abbr"],f"{t['name']} General Manager",personalities[i%len(personalities)],35+(i*7)%60,30+(i*11)%65,"CONTEND" if i%3==0 else "BUILD"))
    for cls in data["draft_classes"]:
        src=source_record(db,cls["source"],cls["url"],"fixture:curated-snapshot",cls,"MEDIUM")
        for p in cls["players"]:
            pid=stable_player_id(None,p["name"],p.get("dob")); db.execute("INSERT OR IGNORE INTO players(id,source_ids,full_name,date_of_birth,nationality,primary_position,level,roster_status,source_record_id,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",(pid,"{}",p["name"],p.get("dob"),p.get("nationality"),p.get("position"),"PROSPECT","DRAFT_ELIGIBLE",src,"MEDIUM"))
            db.execute("INSERT OR REPLACE INTO draft_classes(player_id,draft_year,classification,public_rank,club,league,profile,potential,risk,nhl_eta,source_record_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(pid,cls["year"],"VERIFIED_REAL",p["rank"],p.get("club"),p.get("league"),"UNKNOWN — DATA VERIFICATION REQUIRED","UNKNOWN","UNKNOWN","UNKNOWN",src))
    db.commit()


from __future__ import annotations
import json, os, sqlite3, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("NHLGM_DB", ROOT / "data" / "nhl_gm.sqlite3"))

def connect(path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path); db.row_factory = sqlite3.Row; db.execute("PRAGMA foreign_keys=ON")
    return db

def migrate(db: sqlite3.Connection) -> None:
    db.executescript((Path(__file__).with_name("schema.sql")).read_text())
    db.execute("""INSERT OR IGNORE INTO simulation_contracts
      (simulation_id,contract_id,player_id,team_id,cap_hit,salary,end_season,expiry_status,nmc,ntc,retained_salary,buried_cap)
      SELECT s.id,c.id,c.player_id,c.team_id,c.cap_hit,c.salary,c.end_season,c.expiry_status,c.nmc,c.ntc,c.retained_salary,c.buried_cap
      FROM simulation_state s CROSS JOIN contracts c JOIN players p ON p.id=c.player_id AND p.real_team_id=c.team_id""")
    db.execute("""INSERT OR IGNORE INTO simulation_draft_picks
      (simulation_id,pick_id,draft_year,round,original_owner_id,current_owner_id,conditions,protection,status)
      SELECT s.id,p.id,p.draft_year,p.round,p.original_owner_id,p.current_owner_id,p.conditions,p.protection,p.status
      FROM simulation_state s CROSS JOIN draft_picks p""")
    # Translate rows created by pre-English releases on persistent deployments.
    translations = {
        "Daryl Katz / Ägarkontoret": "Daryl Katz / Owner's Office",
        "Säsongens mandat": "Season mandate",
        "Bygg en hållbar utmanare utan att bryta mot lönetaket.": "Build a sustainable contender without violating the salary cap.",
        "Huvudtränaren": "Head Coach",
        "Första rostermötet": "First roster meeting",
        "Vi behöver fastställa kedjor och special teams inför camp.": "We need to set our lines and special-teams units before camp.",
        "Cap-specialisten": "Cap Specialist",
        "Dataverifiering krävs": "Data verification required",
        "Kontrakt utan verifierad cap hit ligger i verifieringskön och räknas inte som fakta.": "Contracts without a verified cap hit remain in the verification queue and are not treated as facts.",
    }
    for old, new in translations.items():
        for column in ("sender", "subject", "content"):
            db.execute(f"UPDATE inbox SET {column}=? WHERE {column}=?", (new, old))
    db.execute("UPDATE inbox SET actions='[\"Open\",\"Delegate\",\"Postpone\"]' WHERE actions LIKE '%Öppna%'")
    db.execute("UPDATE news SET headline='New Edmonton simulation created' WHERE headline='Ny Edmonton-simulation skapad'")
    db.execute("UPDATE news SET body='The real-world baseline was copied at simulation creation. The alternate timeline begins with the next GM decision.' WHERE body LIKE 'Den verkliga baslinjen kopierades%'")
    db.execute("UPDATE news SET headline=replace(headline,'Ligakontoret:','League office:') WHERE headline LIKE 'Ligakontoret:%'")
    db.execute("UPDATE news SET body='All 32 AI GMs evaluated their rosters, cap positions, and the trade market.' WHERE body='Samtliga 32 AI-GM:ar har utvärderat roster, cap och marknad.'")
    personality_translations = {"Aggressiv contender": "Aggressive contender", "Försiktig konservativ": "Conservative"}
    for old, new in personality_translations.items():
        db.execute("UPDATE gm_profiles SET personality=? WHERE personality=?", (new, old))
    db.commit()

def stable_player_id(nhl_id: int | None, name: str, dob: str | None) -> str:
    if nhl_id: return f"nhl-{nhl_id}"
    return "player-" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"nhlgm:{name}:{dob or 'UNKNOWN'}"))

def rows(db, sql, args=()): return [dict(r) for r in db.execute(sql,args)]
def setting(db,key,default=None):
    r=db.execute("SELECT value FROM metadata WHERE key=?",(key,)).fetchone(); return r[0] if r else default
def set_setting(db,key,value): db.execute("INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))
def json_dump(value): return json.dumps(value,ensure_ascii=False,separators=(",",":"))

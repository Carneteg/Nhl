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
    db.executescript((Path(__file__).with_name("schema.sql")).read_text()); db.commit()

def stable_player_id(nhl_id: int | None, name: str, dob: str | None) -> str:
    if nhl_id: return f"nhl-{nhl_id}"
    return "player-" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"nhlgm:{name}:{dob or 'UNKNOWN'}"))

def rows(db, sql, args=()): return [dict(r) for r in db.execute(sql,args)]
def setting(db,key,default=None):
    r=db.execute("SELECT value FROM metadata WHERE key=?",(key,)).fetchone(); return r[0] if r else default
def set_setting(db,key,value): db.execute("INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))
def json_dump(value): return json.dumps(value,ensure_ascii=False,separators=(",",":"))

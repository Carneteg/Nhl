from __future__ import annotations
import json, os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from .db import connect,migrate,rows,DEFAULT_DB
from .services import active_sim,cap_summary,advance,inbox_action,audits

ROOT=Path(__file__).resolve().parents[1]; STATIC=ROOT/"web"
NAV=[("overview","Översikt"),("inbox","Inkorg"),("news","Nyheter"),("roster","Trupp"),("lines","Kedjor"),("games","Matcher"),("stats","Statistik"),("contracts","Kontrakt"),("cap","Lönetak"),("injuries","Skador"),("waivers","Waivers"),("ahl","Farmarlag"),("prospects","Prospects"),("scouting","Scouting"),("draft","Draft"),("free-agency","Free Agency"),("trades","Trades"),("staff","Personal"),("coach","Tränare"),("owner","Ägare"),("league","Liga"),("teams","Andra lag"),("gms","Andra GM"),("history","Historik"),("settings","Inställningar")]
def snapshot(db):
    sim=active_sim(db); sid=sim["id"] if sim else ""
    roster=rows(db,"SELECT p.id,p.full_name,p.primary_position,p.date_of_birth,p.jersey_number,sp.level,sp.status,sp.morale,sp.form FROM simulation_players sp JOIN players p ON p.id=sp.player_id WHERE sp.simulation_id=? AND sp.team_id='EDM' ORDER BY p.primary_position,p.full_name",(sid,))
    return {"simulation":dict(sim) if sim else None,"cap":cap_summary(db,sid) if sim else {},"roster":roster,"inbox":rows(db,"SELECT * FROM inbox WHERE simulation_id=? ORDER BY id DESC",(sid,)),"news":rows(db,"SELECT * FROM news WHERE simulation_id=? ORDER BY id DESC LIMIT 30",(sid,)),"gms":rows(db,"SELECT * FROM gm_profiles ORDER BY team_id"),"teams":rows(db,"SELECT * FROM teams ORDER BY name"),"draft":rows(db,"SELECT p.full_name,p.primary_position,d.* FROM draft_classes d JOIN players p ON p.id=d.player_id ORDER BY d.draft_year,d.public_rank"),"audit":audits(db,sid) if sim else {},"nav":[{"id":a,"label":b} for a,b in NAV]}
class Handler(BaseHTTPRequestHandler):
    db_path=DEFAULT_DB
    def _json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/state":
            with connect(self.db_path) as db: return self._json(snapshot(db))
        if path=="/health": return self._json({"ok":True})
        file=STATIC/("index.html" if path=="/" else path.lstrip("/"))
        if file.is_file() and STATIC in file.resolve().parents:
            raw=file.read_bytes(); self.send_response(200); self.send_header("Content-Type",{".css":"text/css",".js":"text/javascript",".html":"text/html"}.get(file.suffix,"application/octet-stream")+"; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); return self.wfile.write(raw)
        self.send_error(404)
    def do_POST(self):
        n=int(self.headers.get("Content-Length",0)); body=json.loads(self.rfile.read(n) or b"{}")
        try:
          with connect(self.db_path) as db:
            if self.path=="/api/advance": result={"date":advance(db)}
            elif self.path.startswith("/api/inbox/"): inbox_action(db,int(self.path.rsplit('/',1)[1]),body.get("action","Öppna")); result={"ok":True}
            elif self.path=="/api/roster-action":
                if body.get("action") not in {"AHL","NHL","TRADE_BLOCK","WAIVERS"}: raise ValueError("Invalid action")
                sim=active_sim(db); pid=body["player_id"]
                if body["action"] in {"AHL","NHL"}: db.execute("UPDATE simulation_players SET level=? WHERE simulation_id=? AND player_id=?",(body["action"],sim["id"],pid))
                elif body["action"]=="TRADE_BLOCK": db.execute("UPDATE simulation_players SET trade_block=1 WHERE simulation_id=? AND player_id=?",(sim["id"],pid))
                else: db.execute("INSERT INTO waivers(simulation_id,player_id,status,placed_at) VALUES(?,?,?,date('now'))",(sim["id"],pid,"PENDING"))
                db.commit(); result={"ok":True}
            else: return self._json({"error":"Not found"},404)
          return self._json(result)
        except (ValueError,KeyError) as e: return self._json({"error":str(e)},400)
    def log_message(self,fmt,*args): pass
def serve(host=None,port=None,db_path=DEFAULT_DB):
    host = host or os.environ.get("HOST", "0.0.0.0")
    port = int(port if port is not None else os.environ.get("PORT", "8000"))
    Handler.db_path=db_path
    with connect(db_path) as db: migrate(db)
    print(f"NHL GM web app binding to http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()

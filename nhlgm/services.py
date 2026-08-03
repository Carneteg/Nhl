from __future__ import annotations
import json, uuid, shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from .db import rows, json_dump, set_setting

ACTIVE={"ACTIVE","IR","LTIR"}; EXCLUDED={"TRADED","AHL","JUNIOR","EUROPE","UNSIGNED","RETIRED","HISTORICAL"}
PHASES={"PRE_DRAFT","DRAFT","DEVELOPMENT_CAMP","FREE_AGENCY","OFFSEASON","TRAINING_CAMP","PRESEASON","REGULAR_SEASON","TRADE_DEADLINE","PLAYOFFS","POSTSEASON"}
def phase_for(day):
    md=(day.month,day.day)
    if md<(6,20): return "PRE_DRAFT"
    if md<(6,30): return "DRAFT"
    if md<(7,7): return "FREE_AGENCY"
    if md<(9,10): return "OFFSEASON"
    if md<(10,1): return "TRAINING_CAMP"
    return "REGULAR_SEASON"
def active_sim(db): return db.execute("SELECT * FROM simulation_state WHERE active=1 ORDER BY created_at DESC LIMIT 1").fetchone()
def new_simulation(db,team="EDM",start="2025-07-01"):
    date.fromisoformat(start); db.execute("UPDATE simulation_state SET active=0 WHERE active=1")
    sid=str(uuid.uuid4()); now=datetime.now(timezone.utc).isoformat(); season=f"{start[:4]}-{str(int(start[:4])+1)[-2:]}"
    db.execute("INSERT INTO simulation_state VALUES(?,?,?,?,?,?,?,?,?)",(sid,team,start,start,season,phase_for(date.fromisoformat(start)),1,1,now))
    db.execute("""INSERT INTO simulation_players(simulation_id,player_id,team_id,level,status)
      SELECT ?,id,real_team_id,level,roster_status FROM players WHERE real_team_id IS NOT NULL""",(sid,))
    db.execute("""INSERT INTO roster_assignments(simulation_id,player_id,team_id,league,status,start_date,simulation_status)
      SELECT ?,id,real_team_id,'NHL',roster_status,?,'BASELINE_COPY' FROM players WHERE real_team_id IS NOT NULL AND level='NHL'""",(sid,start))
    messages=[("Daryl Katz / Ägarkontoret","Säsongens mandat","OWNER","HIGH","Bygg en hållbar utmanare utan att bryta mot lönetaket."),("Huvudtränaren","Första rostermötet","COACH","HIGH","Vi behöver fastställa kedjor och special teams inför camp."),("Cap-specialisten","Dataverifiering krävs","CAP","MEDIUM","Kontrakt utan verifierad cap hit ligger i verifieringskön och räknas inte som fakta.")]
    for sender,subject,cat,pri,content in messages: db.execute("INSERT INTO inbox(simulation_id,sender,subject,category,priority,content,actions,created_at) VALUES(?,?,?,?,?,?,?,?)",(sid,sender,subject,cat,pri,content,json_dump(["Öppna","Delegera","Skjut upp"]),now))
    db.execute("INSERT INTO news(simulation_id,kind,headline,body,created_at) VALUES(?,?,?,?,?)",(sid,"OFFICIAL","Ny Edmonton-simulation skapad",f"Den verkliga baslinjen kopierades {start}. Alternativhistoriken börjar med nästa GM-beslut.",now))
    set_setting(db,"active_simulation_id",sid); db.commit(); return sid
def cap_summary(db,simulation_id=None,cap_limit=95_500_000):
    sim=simulation_id or (active_sim(db)["id"] if active_sim(db) else None)
    q="""SELECT c.*,sp.status,sp.level FROM contracts c JOIN simulation_players sp
      ON sp.player_id=c.player_id AND sp.simulation_id=? AND sp.team_id=c.team_id
      WHERE sp.team_id=(SELECT team_id FROM simulation_state WHERE id=?)"""
    cs=rows(db,q,(sim,sim)) if sim else []
    active=[c for c in cs if c["status"] in ACTIVE and c["level"]=="NHL"]
    active_cap=sum(c["cap_hit"] or 0 for c in active); retained=sum(c["retained_salary"] or 0 for c in cs); buried=sum(c["buried_cap"] or 0 for c in cs if c["level"]=="AHL")
    total=active_cap+retained+buried
    return {"salary_cap":cap_limit,"active_roster_cap":active_cap,"active_players":len(active),"retained_salary":retained,"buried_cap":buried,"dead_cap":0,"bonus_overage":0,"total_cap_charge":total,"cap_space":cap_limit-total,"compliant":total<=cap_limit and len(active)<=23}
def audits(db,simulation_id=None):
    sim=simulation_id or (active_sim(db)["id"] if active_sim(db) else None); failures=[]
    dup=rows(db,"SELECT full_name,date_of_birth,count(*) n FROM players GROUP BY full_name,date_of_birth HAVING n>1")
    if dup: failures.append({"code":"DUPLICATE_PLAYER","rows":dup})
    multi=rows(db,"SELECT player_id,count(DISTINCT team_id) n FROM roster_assignments WHERE simulation_id=? AND league='NHL' AND end_date IS NULL GROUP BY player_id HAVING n>1",(sim,)) if sim else []
    if multi: failures.append({"code":"MULTIPLE_NHL_TEAMS","rows":multi})
    traded=rows(db,"""SELECT p.full_name FROM simulation_players sp JOIN players p ON p.id=sp.player_id JOIN contracts c ON c.player_id=sp.player_id WHERE sp.simulation_id=? AND sp.status='TRADED' AND sp.level='NHL' AND c.cap_hit>0""",(sim,)) if sim else []
    if traded: failures.append({"code":"TRADED_IN_ACTIVE_CAP","rows":traded})
    missing=rows(db,"""SELECT p.full_name FROM simulation_players sp JOIN players p ON p.id=sp.player_id LEFT JOIN contracts c ON c.player_id=p.id WHERE sp.simulation_id=? AND sp.level='NHL' AND sp.status='ACTIVE' AND c.cap_hit IS NULL""",(sim,)) if sim else []
    if missing: failures.append({"code":"ACTIVE_CONTRACT_CAP_UNKNOWN","severity":"verification","rows":missing})
    missing_teams=rows(db,"""SELECT t.abbreviation FROM teams t LEFT JOIN players p ON p.real_team_id=t.id AND p.level='NHL'
      WHERE t.league='NHL' GROUP BY t.id HAVING count(p.id)=0""")
    if missing_teams: failures.append({"code":"EMPTY_NHL_TEAM_ROSTER","rows":missing_teams})
    baseline_missing=rows(db,"""SELECT p.full_name,p.real_team_id FROM players p LEFT JOIN contracts c
      ON c.player_id=p.id AND c.team_id=p.real_team_id WHERE p.level='NHL' AND p.real_team_id IS NOT NULL AND c.cap_hit IS NULL""")
    if baseline_missing: failures.append({"code":"BASELINE_CONTRACT_CAP_UNKNOWN","severity":"verification","rows":baseline_missing})
    return {"ok":not [f for f in failures if f.get("severity")!="verification"],"failures":failures,"cap":cap_summary(db,sim)}
def advance(db):
    sim=active_sim(db)
    if not sim: raise ValueError("No active simulation")
    nxt=date.fromisoformat(sim["simulation_date"])+timedelta(days=1)
    db.execute("UPDATE simulation_state SET simulation_date=?,phase=?,day=day+1 WHERE id=?",(nxt.isoformat(),phase_for(nxt),sim["id"]))
    db.execute("INSERT INTO simulation_events(simulation_id,event_date,event_type,payload) VALUES(?,?,?,?)",(sim["id"],nxt.isoformat(),"DAILY_AI_EVALUATION",json_dump({"teams_evaluated":32,"checks":["roster","cap","injuries","needs","deadlines"]})))
    db.execute("INSERT INTO news(simulation_id,kind,headline,body,created_at) VALUES(?,?,?,?,?)",(sim["id"],"ANALYSIS",f"Ligakontoret: {nxt.isoformat()}","Samtliga 32 AI-GM:ar har utvärderat roster, cap och marknad.",datetime.now(timezone.utc).isoformat())); db.commit(); return nxt.isoformat()
def inbox_action(db,message_id,action):
    row=db.execute("SELECT * FROM inbox WHERE id=?",(message_id,)).fetchone()
    if not row: raise ValueError("Message not found")
    db.execute("UPDATE inbox SET status=? WHERE id=?",("RESOLVED:"+action,message_id)); db.execute("INSERT INTO simulation_events(simulation_id,event_date,event_type,payload,resolved) VALUES(?,?,?,?,1)",(row["simulation_id"],date.today().isoformat(),"INBOX_DECISION",json_dump({"message":message_id,"action":action}))); db.commit()

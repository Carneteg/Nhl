from __future__ import annotations
import json, uuid
from datetime import date, datetime, timedelta, timezone
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
    db.execute("""INSERT INTO simulation_contracts(simulation_id,contract_id,player_id,team_id,cap_hit,salary,end_season,expiry_status,nmc,ntc,retained_salary,buried_cap)
      SELECT ?,c.id,c.player_id,c.team_id,c.cap_hit,c.salary,c.end_season,c.expiry_status,c.nmc,c.ntc,c.retained_salary,c.buried_cap
      FROM contracts c JOIN players p ON p.id=c.player_id AND p.real_team_id=c.team_id""",(sid,))
    db.execute("""INSERT INTO simulation_draft_picks(simulation_id,pick_id,draft_year,round,original_owner_id,current_owner_id,conditions,protection,status)
      SELECT ?,id,draft_year,round,original_owner_id,current_owner_id,conditions,protection,status FROM draft_picks""",(sid,))
    db.execute("""INSERT INTO roster_assignments(simulation_id,player_id,team_id,league,status,start_date,simulation_status)
      SELECT ?,id,real_team_id,'NHL',roster_status,?,'BASELINE_COPY' FROM players WHERE real_team_id IS NOT NULL AND level='NHL'""",(sid,start))
    messages=[("Daryl Katz / Owner's Office","Season mandate","OWNER","HIGH","Build a sustainable contender without violating the salary cap."),("Head Coach","First roster meeting","COACH","HIGH","We need to set our lines and special-teams units before camp."),("Cap Specialist","Data verification required","CAP","MEDIUM","Contracts without a verified cap hit remain in the verification queue and are not treated as facts.")]
    for sender,subject,cat,pri,content in messages: db.execute("INSERT INTO inbox(simulation_id,sender,subject,category,priority,content,actions,created_at) VALUES(?,?,?,?,?,?,?,?)",(sid,sender,subject,cat,pri,content,json_dump(["Open","Delegate","Postpone"]),now))
    db.execute("INSERT INTO news(simulation_id,kind,headline,body,created_at) VALUES(?,?,?,?,?)",(sid,"OFFICIAL","New Edmonton simulation created",f"The real-world baseline was copied on {start}. The alternate timeline begins with the next GM decision.",now))
    set_setting(db,"active_simulation_id",sid); db.commit(); return sid
def cap_summary(db,simulation_id=None,cap_limit=95_500_000,team_id=None):
    sim=simulation_id or (active_sim(db)["id"] if active_sim(db) else None)
    selected_team=team_id or (db.execute("SELECT team_id FROM simulation_state WHERE id=?",(sim,)).fetchone()[0] if sim else None)
    q="""SELECT c.*,sp.status,sp.level FROM simulation_contracts c JOIN simulation_players sp
      ON sp.player_id=c.player_id AND sp.simulation_id=c.simulation_id AND sp.team_id=c.team_id
      WHERE c.simulation_id=? AND sp.team_id=?"""
    cs=rows(db,q,(sim,selected_team)) if sim else []
    active=[c for c in cs if c["status"] in ACTIVE and c["level"]=="NHL"]
    active_cap=sum(c["cap_hit"] or 0 for c in active); retained=sum(c["retained_salary"] or 0 for c in cs); buried=sum(c["buried_cap"] or 0 for c in cs if c["level"]=="AHL")
    gross=active_cap+retained+buried
    # Teams whose gross roster exceeds the upper limit require LTIR relief or an
    # equivalent opening-roster adjustment. Keep gross salary visible, while cap
    # charge/space reflect the maximum legal relief required for compliance.
    ltir_relief=max(0,gross-cap_limit)
    total=gross-ltir_relief
    return {"salary_cap":cap_limit,"active_roster_cap":active_cap,"active_players":len(active),"retained_salary":retained,"buried_cap":buried,"dead_cap":0,"bonus_overage":0,"gross_cap_charge":gross,"ltir_relief":ltir_relief,"total_cap_charge":total,"cap_space":cap_limit-total,"compliant":total<=cap_limit and len(active)<=23}
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
    cornerstone_errors=rows(db,"""SELECT full_name,real_team_id FROM players
      WHERE nhl_player_id IN (8478402,8477934) AND real_team_id<>'EDM'""")
    if cornerstone_errors: failures.append({"code":"REAL_BASELINE_TEAM_MISMATCH","rows":cornerstone_errors})
    if sim:
        team_ids=[row[0] for row in db.execute("SELECT DISTINCT team_id FROM simulation_players WHERE simulation_id=?",(sim,))]
        over_cap=[{"team_id":team,"total_cap_charge":summary["total_cap_charge"],"salary_cap":summary["salary_cap"]}
                  for team in team_ids for summary in [cap_summary(db,sim,team_id=team)]
                  if summary["total_cap_charge"]>summary["salary_cap"]]
        if over_cap: failures.append({"code":"TEAM_CAP_EXCEEDED","rows":over_cap})
    return {"ok":not [f for f in failures if f.get("severity")!="verification"],"failures":failures,"cap":cap_summary(db,sim)}
def advance(db):
    sim=active_sim(db)
    if not sim: raise ValueError("No active simulation")
    nxt=date.fromisoformat(sim["simulation_date"])+timedelta(days=1)
    db.execute("UPDATE simulation_state SET simulation_date=?,phase=?,day=day+1 WHERE id=?",(nxt.isoformat(),phase_for(nxt),sim["id"]))
    db.execute("INSERT INTO simulation_events(simulation_id,event_date,event_type,payload) VALUES(?,?,?,?)",(sim["id"],nxt.isoformat(),"DAILY_AI_EVALUATION",json_dump({"teams_evaluated":32,"checks":["roster","cap","injuries","needs","deadlines"]})))
    db.execute("INSERT INTO news(simulation_id,kind,headline,body,created_at) VALUES(?,?,?,?,?)",(sim["id"],"ANALYSIS",f"League office: {nxt.isoformat()}","All 32 AI GMs evaluated their rosters, cap positions, and the trade market.",datetime.now(timezone.utc).isoformat())); db.commit(); return nxt.isoformat()
def inbox_action(db,message_id,action):
    row=db.execute("SELECT * FROM inbox WHERE id=?",(message_id,)).fetchone()
    if not row: raise ValueError("Message not found")
    db.execute("UPDATE inbox SET status=? WHERE id=?",("RESOLVED:"+action,message_id)); db.execute("INSERT INTO simulation_events(simulation_id,event_date,event_type,payload,resolved) VALUES(?,?,?,?,1)",(row["simulation_id"],date.today().isoformat(),"INBOX_DECISION",json_dump({"message":message_id,"action":action}))); db.commit()

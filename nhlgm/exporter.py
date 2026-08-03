from __future__ import annotations
import html, zipfile
from pathlib import Path
from .db import rows
from .services import active_sim,cap_summary,audits

SHEETS=["README","Simulation_State","NHL_Roster","League_Rosters","Roster_Counts","AHL_Roster","Prospects","Contracts","RFA","UFA","Salary_Cap","Depth_Chart","Coaching_Staff","Draft_Capital","Draft_2025","Draft_2026","Future_Draft_Classes","Scouting_Board","Trade_Block","Trade_Centre","Transactions","Injuries","Waivers","Schedule","Standings","Player_Statistics","Team_Statistics","Org_History","Source_Registry","Verification_Queue","Data_Conflicts"]
def _xml(rows_):
 def cell(v): return f'<c t="inlineStr"><is><t>{html.escape(str(v if v is not None else "UNKNOWN"))}</t></is></c>'
 return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+''.join(f'<row r="{i}">'+''.join(cell(v) for v in row)+'</row>' for i,row in enumerate(rows_,1))+'</sheetData></worksheet>'
def export(db,path="exports/Edmonton_Oilers_GM_Simulation_2025_v1.0.xlsx"):
    report=audits(db)
    if not report["ok"]: raise ValueError("Export blocked by quality gates")
    sim=active_sim(db); datasets={s:[[s],["No verified records — see Verification_Queue"]] for s in SHEETS}
    datasets["README"]=[["NHL GM Simulation export"],["Real baseline and simulation state are separate"],["UNKNOWN values require verification"]]
    datasets["Simulation_State"]=[list(dict(sim).keys()),list(dict(sim).values())] if sim else [["No active simulation"]]
    roster=rows(db,"SELECT p.full_name,p.primary_position,p.date_of_birth,p.age_at_start,p.nationality,p.jersey_number,sp.level,sp.status,p.nhl_player_id FROM simulation_players sp JOIN players p ON p.id=sp.player_id WHERE sp.simulation_id=? AND sp.team_id='EDM'",(sim["id"],)) if sim else []
    headers=["Name","Position","DOB","Age at 2025-07-01","Nationality","Number","Level","Status","NHL ID"]
    datasets["NHL_Roster"]=[headers]+[[*r.values()] for r in roster if r["level"]=="NHL"]
    datasets["AHL_Roster"]=[headers]+[[*r.values()] for r in roster if r["level"]=="AHL"]
    league=rows(db,"""SELECT m.team_id,p.full_name,p.primary_position,p.date_of_birth,p.age_at_start,p.nationality,c.cap_hit,c.end_season,c.expiry_status,c.nmc,c.ntc,s.source_url
      FROM season_roster_memberships m JOIN players p ON p.id=m.player_id LEFT JOIN contracts c ON c.player_id=p.id AND c.team_id=m.team_id LEFT JOIN source_records s ON s.id=c.source_record_id
      WHERE m.season='20252026' ORDER BY m.team_id,p.full_name""")
    datasets["League_Rosters"]=[["Team","Name","Position","DOB","Age","Nationality","Cap Hit","Contract End","Expiry","NMC","NTC","Contract Source"]]+[[*r.values()] for r in league]
    counts=rows(db,"SELECT team_id team,count(*) players FROM season_roster_memberships WHERE season='20252026' GROUP BY team_id ORDER BY team_id")
    datasets["Roster_Counts"]=[["Team","Players"]]+[[*r.values()] for r in counts]
    contract_rows=rows(db,"""SELECT c.team_id,p.full_name,c.start_season,c.end_season,c.cap_hit,c.salary,c.contract_type,c.one_two_way,c.expiry_status,c.nmc,c.ntc,c.verification_status,s.source_url
      FROM contracts c JOIN players p ON p.id=c.player_id LEFT JOIN source_records s ON s.id=c.source_record_id ORDER BY c.team_id,p.full_name""")
    datasets["Contracts"]=[["Team","Player","Start","End","Cap Hit","Salary","Type","One/Two-way","Expiry","NMC","NTC","Verification","Source"]]+[[*r.values()] for r in contract_rows]
    datasets["RFA"]=[datasets["Contracts"][0]]+[[*r.values()] for r in contract_rows if r["expiry_status"]=="RFA"]
    datasets["UFA"]=[datasets["Contracts"][0]]+[[*r.values()] for r in contract_rows if r["expiry_status"]=="UFA"]
    c=cap_summary(db); datasets["Salary_Cap"]=[["Metric","Value"]]+[[k,v] for k,v in c.items()]
    sources=rows(db,"SELECT source,source_url,endpoint,fetched_at,verified_at,confidence FROM source_records"); datasets["Source_Registry"]=[list(sources[0])]+[[*r.values()] for r in sources] if sources else [["No source records"]]
    conflicts=rows(db,"SELECT entity_type,entity_id,field,old_value,new_value,recommendation,status FROM data_conflicts"); datasets["Data_Conflicts"]=[list(conflicts[0])]+[[*r.values()] for r in conflicts] if conflicts else [["No open conflicts"]]
    verification=rows(db,"SELECT entity_type,entity_id,field,reason,source_url,status FROM verification_queue ORDER BY entity_type,entity_id")
    datasets["Verification_Queue"]=[["Entity Type","Entity ID","Field","Reason","Source","Status"]]+[[*r.values()] for r in verification]
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): path=path.with_stem(path.stem+"_new")
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
      z.writestr("[Content_Types].xml",'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(SHEETS)+1))+'</Types>')
      z.writestr("_rels/.rels",'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
      z.writestr("xl/workbook.xml",'<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{s}" sheetId="{i}" r:id="rId{i}"/>' for i,s in enumerate(SHEETS,1))+'</sheets></workbook>')
      z.writestr("xl/_rels/workbook.xml.rels",'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(SHEETS)+1))+'</Relationships>')
      for i,s in enumerate(SHEETS,1): z.writestr(f"xl/worksheets/sheet{i}.xml",_xml(datasets[s]))
    return path

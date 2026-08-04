from nhlgm.services import cap_summary, new_simulation
from nhlgm.trades import TradeError, evaluate_trade, execute_trade


def seed_trade_world(db):
    for team in ("EDM", "CGY"):
        db.execute("INSERT INTO teams(id,league,name,abbreviation) VALUES(?,?,?,?)", (team, "NHL", team, team))
    players = [
        ("nhl-97", 97, "Connor McDavid", "1997-01-13", 28, "C", "EDM"),
        ("nhl-29", 29, "Leon Draisaitl", "1995-10-27", 29, "C", "EDM"),
        ("nhl-11", 11, "CPU Forward", "1997-02-01", 28, "C", "CGY"),
        ("nhl-12", 12, "CPU Winger", "1996-02-01", 29, "LW", "CGY"),
    ]
    for player in players:
        db.execute("""INSERT INTO players(id,nhl_player_id,full_name,date_of_birth,age_at_start,primary_position,real_team_id,level,roster_status)
          VALUES(?,?,?,?,?,?,?,?,?)""", (*player, "NHL", "ACTIVE"))
    contracts = [
        ("nhl-97", "EDM", 12_500_000, 2026, 0), ("nhl-29", "EDM", 14_000_000, 2033, 1),
        ("nhl-11", "CGY", 6_000_000, 2028, 0), ("nhl-12", "CGY", 4_000_000, 2027, 0),
    ]
    for player_id,team,cap,end,nmc in contracts:
        db.execute("INSERT INTO contracts(player_id,team_id,start_season,end_season,cap_hit,nmc) VALUES(?,?,?,?,?,?)",
                   (player_id,team,2025,end,cap,nmc))
    db.execute("INSERT INTO draft_picks(id,draft_year,round,original_owner_id,current_owner_id,status) VALUES(1,2026,1,'EDM','EDM','CONFIRMED')")
    db.execute("INSERT INTO draft_picks(id,draft_year,round,original_owner_id,current_owner_id,status) VALUES(2,2026,3,'CGY','CGY','CONFIRMED')")
    db.execute("INSERT INTO draft_picks(id,draft_year,round,original_owner_id,current_owner_id,status) VALUES(3,2027,7,'EDM','EDM','CONFIRMED')")
    db.commit()
    return new_simulation(db, "EDM", "2025-07-01")


def test_real_stars_begin_on_edmonton(db):
    simulation_id = seed_trade_world(db)
    teams = dict(db.execute("SELECT player_id,team_id FROM simulation_players WHERE simulation_id=?", (simulation_id,)))
    assert teams["nhl-97"] == "EDM"
    assert teams["nhl-29"] == "EDM"
    for team in ("EDM", "CGY"):
        cap = cap_summary(db, simulation_id, team_id=team)
        assert cap["total_cap_charge"] > 0
        assert cap["total_cap_charge"] <= cap["salary_cap"]
    gaps = db.execute("""SELECT count(*) FROM simulation_players sp LEFT JOIN simulation_contracts c
      ON c.simulation_id=sp.simulation_id AND c.player_id=sp.player_id AND c.team_id=sp.team_id
      WHERE sp.simulation_id=? AND sp.status='ACTIVE' AND (coalesce(c.cap_hit,0)<=0 OR c.end_season IS NULL)""",
      (simulation_id,)).fetchone()[0]
    assert gaps == 0


def test_balanced_trade_moves_players_contracts_and_picks(db):
    simulation_id = seed_trade_world(db)
    result = execute_trade(db, simulation_id, "EDM", "CGY",
                           user_players=["nhl-97"], cpu_players=["nhl-11"],
                           user_picks=[3], cpu_picks=[2])
    assert result["accepted"]
    assert db.execute("SELECT team_id FROM simulation_players WHERE simulation_id=? AND player_id='nhl-97'", (simulation_id,)).fetchone()[0] == "CGY"
    assert db.execute("SELECT team_id FROM simulation_contracts WHERE simulation_id=? AND player_id='nhl-97'", (simulation_id,)).fetchone()[0] == "CGY"
    assert db.execute("SELECT current_owner_id FROM simulation_draft_picks WHERE simulation_id=? AND pick_id=3", (simulation_id,)).fetchone()[0] == "CGY"
    assert db.execute("SELECT current_owner_id FROM simulation_draft_picks WHERE simulation_id=? AND pick_id=2", (simulation_id,)).fetchone()[0] == "EDM"


def test_cpu_rejects_lopsided_trade(db):
    simulation_id = seed_trade_world(db)
    result = evaluate_trade(db, simulation_id, "EDM", "CGY",
                            user_players=[], cpu_players=["nhl-11"], user_picks=[3], cpu_picks=[])
    assert not result["accepted"]
    assert any("sufficient asset value" in reason for reason in result["reasons"])


def test_no_move_clause_blocks_trade(db):
    simulation_id = seed_trade_world(db)
    try:
        evaluate_trade(db, simulation_id, "EDM", "CGY",
                       user_players=["nhl-29"], cpu_players=["nhl-11"])
        assert False
    except TradeError as error:
        assert "no-move clause" in str(error)


def test_cpu_rejects_trade_that_breaks_salary_cap(db):
    simulation_id = seed_trade_world(db)
    db.execute("UPDATE simulation_contracts SET cap_hit=90000000 WHERE simulation_id=? AND player_id='nhl-12'", (simulation_id,))
    db.commit()
    result = evaluate_trade(db, simulation_id, "EDM", "CGY",
                            user_players=["nhl-97"], cpu_players=["nhl-11"],
                            user_picks=[3], cpu_picks=[2])
    assert not result["accepted"]
    assert any("salary cap" in reason for reason in result["reasons"])

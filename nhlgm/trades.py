"""Simulation-only player and draft-pick trades with conservative CPU valuation."""
from __future__ import annotations

from datetime import datetime, timezone

from .db import json_dump, rows
from .services import cap_summary


class TradeError(ValueError):
    pass


def _player_asset(db, simulation_id, player_id, owner):
    row = db.execute("""SELECT p.id,p.full_name,p.age_at_start,p.primary_position,sp.team_id,
      c.cap_hit,c.end_season,c.nmc,c.ntc FROM simulation_players sp JOIN players p ON p.id=sp.player_id
      LEFT JOIN simulation_contracts c ON c.simulation_id=sp.simulation_id AND c.player_id=sp.player_id AND c.team_id=sp.team_id
      WHERE sp.simulation_id=? AND sp.player_id=?""", (simulation_id, player_id)).fetchone()
    if not row or row["team_id"] != owner:
        raise TradeError(f"{player_id} is not controlled by {owner}")
    if row["nmc"]:
        raise TradeError(f"{row['full_name']} has a no-move clause")
    if row["ntc"]:
        raise TradeError(f"{row['full_name']} has a no-trade clause that has not been waived")
    age = row["age_at_start"] or 27
    # Transparent, deliberately conservative heuristic. Youth, premium positions,
    # and manageable contracts raise value; age and large cap commitments reduce it.
    value = 35 + max(-18, min(18, (29 - age) * 3))
    if row["primary_position"] in {"C", "D", "G"}:
        value += 5
    cap_hit = row["cap_hit"] or 0
    value += min(60, cap_hit / 1_000_000 * 5)
    value -= max(0, cap_hit - 12_000_000) / 1_000_000 * 2
    return dict(row), max(12.0, round(value, 2))


def _pick_asset(db, simulation_id, pick_id, owner):
    row = db.execute("SELECT * FROM simulation_draft_picks WHERE simulation_id=? AND pick_id=?",
                     (simulation_id, pick_id)).fetchone()
    if not row or row["current_owner_id"] != owner:
        raise TradeError(f"Draft pick {pick_id} is not controlled by {owner}")
    if row["status"] != "CONFIRMED":
        raise TradeError(f"Draft pick {pick_id} is conditional and cannot be traded as confirmed")
    values = {1: 70, 2: 38, 3: 24, 4: 15, 5: 10, 6: 7, 7: 5}
    return dict(row), float(values.get(row["round"], 3))


def _side(db, simulation_id, team, player_ids, pick_ids):
    players = [_player_asset(db, simulation_id, pid, team) for pid in player_ids]
    picks = [_pick_asset(db, simulation_id, int(pid), team) for pid in pick_ids]
    return {"players": [p[0] for p in players], "picks": [p[0] for p in picks],
            "value": round(sum(p[1] for p in players) + sum(p[1] for p in picks), 2)}


def evaluate_trade(db, simulation_id, user_team, cpu_team, user_players=(), cpu_players=(),
                   user_picks=(), cpu_picks=()):
    if not cpu_team or user_team == cpu_team:
        raise TradeError("Select a different trade partner")
    if not (user_players or cpu_players or user_picks or cpu_picks):
        raise TradeError("A trade must contain at least one asset")
    outgoing = _side(db, simulation_id, user_team, user_players, user_picks)
    incoming = _side(db, simulation_id, cpu_team, cpu_players, cpu_picks)
    if not (outgoing["players"] or outgoing["picks"]) or not (incoming["players"] or incoming["picks"]):
        raise TradeError("Both teams must exchange at least one asset")
    user_cap_before = cap_summary(db, simulation_id, team_id=user_team)
    cpu_cap_before = cap_summary(db, simulation_id, team_id=cpu_team)
    user_delta = sum((p["cap_hit"] or 0) for p in incoming["players"]) - sum((p["cap_hit"] or 0) for p in outgoing["players"])
    cpu_delta = -user_delta
    user_after = user_cap_before["total_cap_charge"] + user_delta
    cpu_after = cpu_cap_before["total_cap_charge"] + cpu_delta
    cap_limit = user_cap_before["salary_cap"]
    reasons = []
    if user_after > cap_limit:
        reasons.append(f"{user_team} would exceed the salary cap")
    if cpu_after > cap_limit:
        reasons.append(f"{cpu_team} would exceed the salary cap")
    # CPU requires a 7% premium and rejects severe roster-count imbalance.
    if outgoing["value"] < incoming["value"] * 1.07:
        reasons.append(f"{cpu_team} is not receiving sufficient asset value")
    if outgoing["value"] > incoming["value"] * 1.45:
        reasons.append("The offer is too lopsided to be considered a realistic hockey trade")
    player_balance = len(outgoing["players"]) - len(incoming["players"])
    if abs(player_balance) > 2:
        reasons.append("The trade creates an unrealistic roster imbalance")
    cpu_roster = rows(db,"SELECT p.primary_position FROM simulation_players sp JOIN players p ON p.id=sp.player_id WHERE sp.simulation_id=? AND sp.team_id=? AND sp.status='ACTIVE'",(simulation_id,cpu_team))
    if len(cpu_roster) >= 18:
        positions=[p["primary_position"] for p in cpu_roster]
        for player in incoming["players"]: positions.append(player["primary_position"])
        for player in outgoing["players"]:
            if player["primary_position"] in positions: positions.remove(player["primary_position"])
        if positions.count("G") < 2 or sum(p == "D" for p in positions) < 6:
            reasons.append(f"{cpu_team} would create an unacceptable positional need")
    accepted = not reasons
    return {"accepted": accepted, "reasons": reasons, "user_team": user_team, "cpu_team": cpu_team,
            "user_sends": outgoing, "cpu_sends": incoming,
            "cap": {user_team: {"before": user_cap_before["total_cap_charge"], "after": user_after},
                    cpu_team: {"before": cpu_cap_before["total_cap_charge"], "after": cpu_after}}}


def execute_trade(db, simulation_id, user_team, cpu_team, **assets):
    evaluation = evaluate_trade(db, simulation_id, user_team, cpu_team, **assets)
    now = datetime.now(timezone.utc).isoformat()
    offer = json_dump(assets)
    status = "ACCEPTED" if evaluation["accepted"] else "REJECTED"
    db.execute("INSERT INTO trade_negotiations(simulation_id,from_team,to_team,offer,status,interest,created_at) VALUES(?,?,?,?,?,?,?)",
               (simulation_id, user_team, cpu_team, offer, status, 100 if evaluation["accepted"] else 20, now))
    if not evaluation["accepted"]:
        db.commit()
        return evaluation
    for player in evaluation["user_sends"]["players"]:
        db.execute("UPDATE simulation_players SET team_id=? WHERE simulation_id=? AND player_id=?", (cpu_team, simulation_id, player["id"]))
        db.execute("UPDATE simulation_contracts SET team_id=? WHERE simulation_id=? AND player_id=? AND team_id=?", (cpu_team, simulation_id, player["id"], user_team))
    for player in evaluation["cpu_sends"]["players"]:
        db.execute("UPDATE simulation_players SET team_id=? WHERE simulation_id=? AND player_id=?", (user_team, simulation_id, player["id"]))
        db.execute("UPDATE simulation_contracts SET team_id=? WHERE simulation_id=? AND player_id=? AND team_id=?", (user_team, simulation_id, player["id"], cpu_team))
    for pick in evaluation["user_sends"]["picks"]:
        db.execute("UPDATE simulation_draft_picks SET current_owner_id=? WHERE simulation_id=? AND pick_id=?", (cpu_team, simulation_id, pick["pick_id"]))
    for pick in evaluation["cpu_sends"]["picks"]:
        db.execute("UPDATE simulation_draft_picks SET current_owner_id=? WHERE simulation_id=? AND pick_id=?", (user_team, simulation_id, pick["pick_id"]))
    db.execute("INSERT INTO transactions(simulation_id,date,type,teams,players,picks,simulation_or_real,canon_status) VALUES(?,?,?,?,?,?,?,?)",
               (simulation_id, now[:10], "TRADE", json_dump([user_team, cpu_team]),
                json_dump(list(assets.get("user_players", ())) + list(assets.get("cpu_players", ()))),
                json_dump(list(assets.get("user_picks", ())) + list(assets.get("cpu_picks", ()))), "SIMULATION", "GM_DECISION"))
    db.commit()
    return evaluation

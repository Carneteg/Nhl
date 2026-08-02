"""Simulation and roster transaction domain services."""
import random
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Game, Player, SaveGame, Standing, Team, Trade

def team_strength(db: Session, team_id: int) -> float:
    players = db.scalars(select(Player).where(Player.team_id == team_id)).all()
    if not players: return 50.0
    return sum(p.overall * .72 + p.morale * .1 + p.form * .12 - p.fatigue * .06 for p in players) / len(players)

def simulate_day(db: Session, save: SaveGame) -> list[Game]:
    """Simulate a league day; seeded state makes outcomes reproducible per save/day."""
    teams = list(db.scalars(select(Team).order_by(Team.id)))
    rng = random.Random(save.id * 100_000 + save.season * 100 + save.day)
    rng.shuffle(teams); games = []
    for home, away in zip(teams[::2], teams[1::2]):
        hs, aws = team_strength(db, home.id) + 1.4, team_strength(db, away.id)
        home_goals = max(0, round(rng.gauss(3 + (hs-70)/12, 1.25)))
        away_goals = max(0, round(rng.gauss(3 + (aws-70)/12, 1.25)))
        overtime = home_goals == away_goals
        if overtime: (home_goals, away_goals) = (home_goals + 1, away_goals) if rng.random() < hs/(hs+aws) else (home_goals, away_goals + 1)
        game = Game(save_id=save.id, day=save.day, home_team_id=home.id, away_team_id=away.id, home_score=home_goals, away_score=away_goals, overtime=overtime)
        db.add(game); games.append(game)
        for team, gf, ga in ((home,home_goals,away_goals),(away,away_goals,home_goals)):
            standing = db.scalar(select(Standing).where(Standing.save_id==save.id, Standing.team_id==team.id))
            standing.games += 1; standing.goals_for += gf; standing.goals_against += ga
            if gf > ga: standing.wins += 1
            elif overtime: standing.overtime_losses += 1
            else: standing.losses += 1
    save.day += 1; db.commit()
    return games

def execute_trade(db: Session, save_id: int, from_team: int, to_team: int, from_player: int, to_player: int) -> tuple[bool,str,float]:
    """Evaluate asset value, clauses, ownership and post-trade cap compliance."""
    a, b = db.get(Player, from_player), db.get(Player, to_player)
    if not a or not b or a.team_id != from_team or b.team_id != to_team: return False, 'Spelarna tillhör inte de angivna lagen.', 0
    if a.no_move or b.no_move: return False, 'En spelare har en no-move-klausul.', 0
    value = lambda p: p.overall * 1.4 + p.potential * .8 - p.age * .35 - p.cap_hit / 1_000_000 * 1.8
    difference = round(value(a)-value(b), 2)
    if difference < -8: accepted, reason = False, 'Motståndarlaget kräver mer värde.'
    else:
        cap_a = sum(p.cap_hit for p in db.scalars(select(Player).where(Player.team_id==from_team))) - a.cap_hit + b.cap_hit
        cap_b = sum(p.cap_hit for p in db.scalars(select(Player).where(Player.team_id==to_team))) - b.cap_hit + a.cap_hit
        ta, tb = db.get(Team, from_team), db.get(Team, to_team)
        accepted = cap_a <= ta.salary_cap and cap_b <= tb.salary_cap
        reason = 'Trade accepterad.' if accepted else 'Traden bryter mot salary cap.'
        if accepted: a.team_id, b.team_id = to_team, from_team
    db.add(Trade(save_id=save_id, from_team_id=from_team, to_team_id=to_team, player_from_id=from_player, player_to_id=to_player, accepted=accepted, value_difference=difference)); db.commit()
    return accepted, reason, difference

"""Idempotent synthetic league seed used by local careers."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Player, Team

TEAMS = [
('Anaheim Ducks','ANA','Anaheim','West','Pacific'),('Boston Bruins','BOS','Boston','East','Atlantic'),('Buffalo Sabres','BUF','Buffalo','East','Atlantic'),('Calgary Flames','CGY','Calgary','West','Pacific'),('Carolina Hurricanes','CAR','Raleigh','East','Metropolitan'),('Chicago Blackhawks','CHI','Chicago','West','Central'),('Colorado Avalanche','COL','Denver','West','Central'),('Columbus Blue Jackets','CBJ','Columbus','East','Metropolitan'),('Dallas Stars','DAL','Dallas','West','Central'),('Detroit Red Wings','DET','Detroit','East','Atlantic'),('Edmonton Oilers','EDM','Edmonton','West','Pacific'),('Florida Panthers','FLA','Sunrise','East','Atlantic'),('Los Angeles Kings','LAK','Los Angeles','West','Pacific'),('Minnesota Wild','MIN','Saint Paul','West','Central'),('Montreal Canadiens','MTL','Montreal','East','Atlantic'),('Nashville Predators','NSH','Nashville','West','Central'),('New Jersey Devils','NJD','Newark','East','Metropolitan'),('New York Islanders','NYI','Elmont','East','Metropolitan'),('New York Rangers','NYR','New York','East','Metropolitan'),('Ottawa Senators','OTT','Ottawa','East','Atlantic'),('Philadelphia Flyers','PHI','Philadelphia','East','Metropolitan'),('Pittsburgh Penguins','PIT','Pittsburgh','East','Metropolitan'),('San Jose Sharks','SJS','San Jose','West','Pacific'),('Seattle Kraken','SEA','Seattle','West','Pacific'),('St. Louis Blues','STL','St. Louis','West','Central'),('Tampa Bay Lightning','TBL','Tampa','East','Atlantic'),('Toronto Maple Leafs','TOR','Toronto','East','Atlantic'),('Utah Mammoth','UTA','Salt Lake City','West','Central'),('Vancouver Canucks','VAN','Vancouver','West','Pacific'),('Vegas Golden Knights','VGK','Las Vegas','West','Pacific'),('Washington Capitals','WSH','Washington','East','Metropolitan'),('Winnipeg Jets','WPG','Winnipeg','West','Central')]

def seed_league(db: Session) -> None:
    """Create clubs and balanced generated players once."""
    if db.scalar(select(Team.id).limit(1)):
        return
    for index, data in enumerate(TEAMS):
        team = Team(name=data[0], abbreviation=data[1], city=data[2], conference=data[3], division=data[4])
        db.add(team); db.flush()
        positions = ['C','LW','RW','D','D','G']
        for slot, position in enumerate(positions):
            rating = 69 + ((index * 3 + slot * 4) % 18)
            db.add(Player(name=f'{data[1]} Player {slot + 1}', position=position, age=21 + (index + slot) % 14,
                height_cm=178 + (index + slot) % 18, weight_kg=78 + (index * 2 + slot) % 20,
                nationality=['Canada','USA','Sweden','Finland'][index % 4], team_id=team.id,
                cap_hit=900_000 + max(0, rating - 68) * 380_000, contract_years=1 + slot % 5,
                potential=min(95, rating + 8), offense=rating + (2 if position != 'D' else -2),
                defense=rating + (3 if position == 'D' else -1), hockey_iq=rating, shooting=rating,
                skating=rating + 1, physical=rating - 1, leadership=45 + slot * 5))
    db.commit()

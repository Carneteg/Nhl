"""Core persistent domain model for the MVP."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    abbreviation: Mapped[str] = mapped_column(String(3), unique=True)
    city: Mapped[str] = mapped_column(String(60))
    conference: Mapped[str] = mapped_column(String(10))
    division: Mapped[str] = mapped_column(String(15))
    salary_cap: Mapped[int] = mapped_column(default=88_000_000)
    players: Mapped[list["Player"]] = relationship(back_populates="team")

class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), index=True)
    position: Mapped[str] = mapped_column(String(2))
    age: Mapped[int]
    height_cm: Mapped[int]
    weight_kg: Mapped[int]
    nationality: Mapped[str] = mapped_column(String(40))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    cap_hit: Mapped[int] = mapped_column(default=0)
    contract_years: Mapped[int] = mapped_column(default=1)
    no_move: Mapped[bool] = mapped_column(Boolean, default=False)
    no_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    potential: Mapped[int] = mapped_column(default=70)
    offense: Mapped[int] = mapped_column(default=60)
    defense: Mapped[int] = mapped_column(default=60)
    hockey_iq: Mapped[int] = mapped_column(default=60)
    shooting: Mapped[int] = mapped_column(default=60)
    skating: Mapped[int] = mapped_column(default=60)
    physical: Mapped[int] = mapped_column(default=60)
    discipline: Mapped[int] = mapped_column(default=60)
    aggression: Mapped[int] = mapped_column(default=60)
    morale: Mapped[int] = mapped_column(default=70)
    leadership: Mapped[int] = mapped_column(default=50)
    fatigue: Mapped[int] = mapped_column(default=0)
    form: Mapped[int] = mapped_column(default=50)
    play_style: Mapped[str] = mapped_column(String(30), default="Two-way")
    development_curve: Mapped[str] = mapped_column(String(20), default="Normal")
    team: Mapped[Team | None] = relationship(back_populates="players")

    @property
    def overall(self) -> int:
        """Calculate overall from skills rather than storing a stale value."""
        skills = [self.offense, self.defense, self.hockey_iq, self.shooting, self.skating, self.physical]
        return round(sum(skills) / len(skills))

class SaveGame(Base):
    __tablename__ = "save_games"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    user_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    season: Mapped[int] = mapped_column(default=2026)
    day: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_team: Mapped[Team] = relationship()

class Standing(Base):
    __tablename__ = "standings"
    __table_args__ = (UniqueConstraint("save_id", "team_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    save_id: Mapped[int] = mapped_column(ForeignKey("save_games.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    games: Mapped[int] = mapped_column(default=0)
    wins: Mapped[int] = mapped_column(default=0)
    losses: Mapped[int] = mapped_column(default=0)
    overtime_losses: Mapped[int] = mapped_column(default=0)
    goals_for: Mapped[int] = mapped_column(default=0)
    goals_against: Mapped[int] = mapped_column(default=0)
    team: Mapped[Team] = relationship()

class Game(Base):
    __tablename__ = "games"
    id: Mapped[int] = mapped_column(primary_key=True)
    save_id: Mapped[int] = mapped_column(ForeignKey("save_games.id"))
    day: Mapped[int]
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_score: Mapped[int]
    away_score: Mapped[int]
    overtime: Mapped[bool] = mapped_column(default=False)

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    save_id: Mapped[int] = mapped_column(ForeignKey("save_games.id"))
    from_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    to_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    player_from_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    player_to_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    accepted: Mapped[bool]
    value_difference: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

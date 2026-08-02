"""Validated REST request and response shapes."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; abbreviation: str; city: str; conference: str; division: str; salary_cap: int

class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; position: str; age: int; nationality: str; cap_hit: int; contract_years: int
    no_move: bool; no_trade: bool; potential: int; overall: int; morale: int; play_style: str

class SaveCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    team_id: int

class SaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; season: int; day: int; user_team: TeamOut; updated_at: datetime

class TradeRequest(BaseModel):
    from_team_id: int; to_team_id: int; player_from_id: int; player_to_id: int

class TradeResult(BaseModel):
    accepted: bool; reason: str; value_difference: float

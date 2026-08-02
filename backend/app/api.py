"""Versioned HTTP API for game clients."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db
from .models import Player, SaveGame, Standing, Team
from .schemas import PlayerOut, SaveCreate, SaveOut, TeamOut, TradeRequest, TradeResult
from .services import execute_trade, simulate_day

router = APIRouter(prefix='/api')

@router.get('/teams', response_model=list[TeamOut])
def teams(db: Session=Depends(get_db)): return db.scalars(select(Team).order_by(Team.name)).all()

@router.get('/teams/{team_id}/roster', response_model=list[PlayerOut])
def roster(team_id: int, db: Session=Depends(get_db)): return db.scalars(select(Player).where(Player.team_id==team_id).order_by(Player.position, Player.name)).all()

@router.get('/saves', response_model=list[SaveOut])
def saves(db: Session=Depends(get_db)): return db.scalars(select(SaveGame).order_by(SaveGame.updated_at.desc())).all()

@router.post('/saves', response_model=SaveOut, status_code=201)
def create_save(payload: SaveCreate, db: Session=Depends(get_db)):
    if not db.get(Team, payload.team_id): raise HTTPException(404, 'Team not found')
    save = SaveGame(name=payload.name, user_team_id=payload.team_id); db.add(save); db.flush()
    for team_id in db.scalars(select(Team.id)): db.add(Standing(save_id=save.id, team_id=team_id))
    db.commit(); db.refresh(save); return save

@router.get('/saves/{save_id}/standings')
def standings(save_id: int, db: Session=Depends(get_db)):
    rows=db.scalars(select(Standing).where(Standing.save_id==save_id).order_by((Standing.wins*2+Standing.overtime_losses).desc())).all()
    return [{'team':r.team.abbreviation,'games':r.games,'wins':r.wins,'losses':r.losses,'otl':r.overtime_losses,'points':r.wins*2+r.overtime_losses,'gf':r.goals_for,'ga':r.goals_against} for r in rows]

@router.post('/saves/{save_id}/simulate')
def simulate(save_id: int, db: Session=Depends(get_db)):
    save=db.get(SaveGame,save_id)
    if not save: raise HTTPException(404,'Save not found')
    games=simulate_day(db,save)
    return {'day':save.day,'games':[{'home':db.get(Team,g.home_team_id).abbreviation,'away':db.get(Team,g.away_team_id).abbreviation,'score':f'{g.home_score}–{g.away_score}','overtime':g.overtime} for g in games]}

@router.post('/saves/{save_id}/trades', response_model=TradeResult)
def trade(save_id:int,payload:TradeRequest,db:Session=Depends(get_db)):
    if not db.get(SaveGame,save_id): raise HTTPException(404,'Save not found')
    accepted,reason,difference=execute_trade(db,save_id,payload.from_team_id,payload.to_team_id,payload.player_from_id,payload.player_to_id)
    return TradeResult(accepted=accepted,reason=reason,value_difference=difference)

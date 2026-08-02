"""End-to-end tests for the playable MVP loop."""
import os
os.environ['DATABASE_URL']='sqlite:///./test.db'
from fastapi.testclient import TestClient
from app.main import app

def test_create_simulate_and_trade():
    with TestClient(app) as client:
        teams=client.get('/api/teams').json(); assert len(teams)==32
        save=client.post('/api/saves',json={'name':'Test career','team_id':teams[0]['id']})
        assert save.status_code==201
        result=client.post(f"/api/saves/{save.json()['id']}/simulate").json()
        assert len(result['games'])==16 and result['day']==2
        standings=client.get(f"/api/saves/{save.json()['id']}/standings").json()
        assert len(standings)==32 and sum(x['games'] for x in standings)==32

def test_overall_is_calculated():
    with TestClient(app) as client:
        team=client.get('/api/teams').json()[0]
        player=client.get(f"/api/teams/{team['id']}/roster").json()[0]
        assert 60 <= player['overall'] <= 99

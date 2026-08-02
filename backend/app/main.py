"""FastAPI application lifecycle and middleware."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
from .database import Base, SessionLocal, engine
from .seed import seed_league

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db: seed_league(db)
    yield

app=FastAPI(title='Puck Dynasty API',version='0.1.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:3000'],allow_methods=['*'],allow_headers=['*'])
app.include_router(router)

@app.get('/health')
def health(): return {'status':'ok'}

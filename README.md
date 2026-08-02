# Puck Dynasty

Puck Dynasty is a local-first, text-based NHL general manager simulator. The MVP lets you create multiple careers, choose any of the 32 NHL clubs, inspect a database-driven roster and salary cap, simulate games, and complete cap-aware trades. Every action is persisted in SQLite so a career resumes exactly where it stopped.

## Quick start with Docker

```bash
docker compose up --build
```

Open <http://localhost:3000>. The API and interactive documentation are available at <http://localhost:8000/docs>.

## Local development

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Run backend tests with `cd backend && pytest`.

## Architecture

- `backend/app/models.py`: persistent league, save, roster, contract, game and trade entities.
- `backend/app/services/`: deterministic simulation and trade evaluation business rules.
- `backend/app/api.py`: versioned REST endpoints; suitable for a future multiplayer client.
- `frontend/`: responsive Next.js dashboard using Tailwind CSS.

The included seed is synthetic and intentionally contains no licensed player data. It creates all NHL teams and representative generated rosters; richer datasets can be imported without changing game logic.


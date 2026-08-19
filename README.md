# Citizen Bridge

Your agent across all Indian public services.

This monorepo contains a FastAPI backend and a Next.js frontend. The current
foundation exposes a health endpoint and a placeholder UI that reports whether
the API is available.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer and npm
- Docker with Compose (optional)

## Run locally

Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --env-file .env
```

The API is available at <http://localhost:8000>; `GET /health` returns
`{"status":"ok"}`.

In a second terminal, start the frontend:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open <http://localhost:3000>. The page displays **Citizen Bridge** and the API
health status.

## Run checks

```bash
cd backend
ruff check .
ruff format --check .
mypy app/
pytest
```

```bash
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

## Run with Docker

Copy `.env.example` to `.env` if you need to override any defaults, then run:

```bash
docker compose up --build
```

The frontend is exposed on port 3000 and the backend on port 8000. Backend data
is stored in the named `citizen_bridge_data` volume and survives container
restarts.

For bind-mounted source and hot reload in both services:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Stop either stack with `docker compose down`. Add `--volumes` only when you
intentionally want to remove persisted local data.

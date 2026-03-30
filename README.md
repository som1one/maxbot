# Telegram Bot with Admin Panel (FastAPI) + PostgreSQL + Docker

Replicates core behavior of `@kvtservice_bot`:
- Collects applications from Telegram users
- Persists to PostgreSQL
- Sends each application to a configured Telegram chat ID and to an email selected in admin panel
- Admin panel (FastAPI) to manage settings and view applications

## Quick start

1) Copy environment file
```bash
cp .env.example .env
```

2) Build and run
```bash
docker compose up -d --build
```

3) Open admin web UI: `http://localhost:8000` (docs at `/docs`)
   - Basic auth with `ADMIN_USERNAME`/`ADMIN_PASSWORD`

## Services
- backend: FastAPI app (admin panel + REST)
- bot: Telegram bot worker (aiogram)
- db: PostgreSQL
- mailhog: local email testing (web UI at http://localhost:8025)

## Tech stack
- FastAPI, SQLAlchemy 2.0
- aiogram 3.x
- Postgres 15
- Uvicorn

## Configuration
See `.env.example` for all options.

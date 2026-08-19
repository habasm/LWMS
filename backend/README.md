# LWMS API

## Run locally

1. Create PostgreSQL database `lwms` and copy `.env.example` to `.env`.
2. `python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt`
3. `alembic upgrade head`
4. `python -m app.seed`
5. `uvicorn app.main:app --reload`

OpenAPI is served at `/docs`. All development login accounts are documented in `../docs/DEMO_CREDENTIALS.md`.

# LWMS architecture

The API uses a layered FastAPI design: routers handle transport concerns, SQLAlchemy models own persistence, Pydantic schemas validate requests, and `dependencies.py` provides JWT identity and role checks. API paths are versioned under `/api/v1`.

## Roles

`super_admin` administers people, resources, class/project schedules, and project approvals. Facility assistants and instructors can submit internal or external stakeholder project requests. Maintainers/technicians progress maintenance work. Student accounts are intentionally unnecessary because teaching schedules target named classes or groups.

## Core API resources

`/auth`, `/users`, `/facilities`, `/equipment`, `/maintenance`, `/projects`, `/schedules`, `/requests`, `/announcements`, and `/dashboard` provide the operational surface. List endpoints return a consistent `data` + `meta` envelope and accept `skip`, `limit`, and where applicable `search`.

## Development

PostgreSQL is the production target. SQLite is deliberately supported for local evaluation. Run migrations with `alembic upgrade head`, seed with `python -m app.seed`, then serve with `uvicorn app.main:app --reload`.

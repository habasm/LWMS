from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from sqlalchemy import inspect
from .core.config import settings
from .core.database import Base, engine
from . import models
from .router import api
from .seed import seed
app=FastAPI(title='LWMS API',version='1.0.0',description='Laboratory and Workshop Management System')
app.add_middleware(CORSMiddleware,allow_origins=settings().origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.include_router(api)
@app.get('/health',tags=['health'])
def health(): return {'status':'ok'}
@app.on_event('startup')
def create_development_tables():
    # SQLite is intentionally zero-config for local development. PostgreSQL
    # environments should use `alembic upgrade head` before starting the API.
    if settings().database_url.startswith('sqlite'):
        Base.metadata.create_all(engine)
        # Lightweight development compatibility for databases created before
        # the first-login password-change policy was introduced.
        user_columns={c['name'] for c in inspect(engine).get_columns('users')}
        if 'must_change_password' not in user_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql('ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0')
        if 'assigned_facility_id' not in user_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql('ALTER TABLE users ADD COLUMN assigned_facility_id INTEGER')
        resource_columns={c['name'] for c in inspect(engine).get_columns('facility_resources')}
        with engine.begin() as connection:
            if 'accepted' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN accepted BOOLEAN NOT NULL DEFAULT 0')
            if 'archived' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0')
            if 'checked_by_id' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN checked_by_id INTEGER')
            if 'checked_at' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN checked_at DATETIME')
            if 'review_status' not in resource_columns: connection.exec_driver_sql("ALTER TABLE facility_resources ADD COLUMN review_status VARCHAR(20) NOT NULL DEFAULT 'pending'")
            if 'review_notes' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN review_notes TEXT')
            if 'revision' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN revision INTEGER NOT NULL DEFAULT 1')
            if 'submitted_by_id' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN submitted_by_id INTEGER')
            if 'last_accepted_snapshot' not in resource_columns: connection.exec_driver_sql('ALTER TABLE facility_resources ADD COLUMN last_accepted_snapshot JSON')
        maintenance_columns={c['name'] for c in inspect(engine).get_columns('maintenance_requests')}
        with engine.begin() as connection:
            if 'resource_id' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN resource_id INTEGER')
            if 'facility_id' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN facility_id INTEGER')
            if 'resolution' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN resolution VARCHAR(30)')
            if 'assistant_verification' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN assistant_verification VARCHAR(30)')
            if 'verification_notes' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN verification_notes TEXT')
            if 'verified_at' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN verified_at DATETIME')
            if 'parent_request_id' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN parent_request_id INTEGER')
            if 'asset_id' not in maintenance_columns: connection.exec_driver_sql('ALTER TABLE maintenance_requests ADD COLUMN asset_id INTEGER')
        usage_columns={c['name'] for c in inspect(engine).get_columns('equipment_usage_requests')}
        if 'usage_type' not in usage_columns:
            with engine.begin() as connection:
                connection.exec_driver_sql("ALTER TABLE equipment_usage_requests ADD COLUMN usage_type VARCHAR(20) NOT NULL DEFAULT 'consumed'")
        project_columns={c['name'] for c in inspect(engine).get_columns('projects')}
        with engine.begin() as connection:
            if 'stakeholder_name' not in project_columns: connection.exec_driver_sql('ALTER TABLE projects ADD COLUMN stakeholder_name VARCHAR(160)')
            if 'organization' not in project_columns: connection.exec_driver_sql('ALTER TABLE projects ADD COLUMN organization VARCHAR(180)')
            if 'contact_email' not in project_columns: connection.exec_driver_sql('ALTER TABLE projects ADD COLUMN contact_email VARCHAR(255)')
            if 'requested_by_id' not in project_columns: connection.exec_driver_sql('ALTER TABLE projects ADD COLUMN requested_by_id INTEGER')
            if 'approval_status' not in project_columns: connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'approved'")
            if 'approval_notes' not in project_columns: connection.exec_driver_sql('ALTER TABLE projects ADD COLUMN approval_notes TEXT')
            if 'approved_by_id' not in project_columns: connection.exec_driver_sql('ALTER TABLE projects ADD COLUMN approved_by_id INTEGER')
            if 'approved_at' not in project_columns: connection.exec_driver_sql('ALTER TABLE projects ADD COLUMN approved_at DATETIME')
        schedule_columns={c['name'] for c in inspect(engine).get_columns('schedules')}
        with engine.begin() as connection:
            if 'schedule_type' not in schedule_columns: connection.exec_driver_sql("ALTER TABLE schedules ADD COLUMN schedule_type VARCHAR(20) NOT NULL DEFAULT 'class'")
            if 'project_id' not in schedule_columns: connection.exec_driver_sql('ALTER TABLE schedules ADD COLUMN project_id INTEGER')
            if 'notes' not in schedule_columns: connection.exec_driver_sql('ALTER TABLE schedules ADD COLUMN notes TEXT')
            if 'schedule_days' not in schedule_columns: connection.exec_driver_sql("ALTER TABLE schedules ADD COLUMN schedule_days JSON NOT NULL DEFAULT '[]'")
            if 'period_start' not in schedule_columns: connection.exec_driver_sql('ALTER TABLE schedules ADD COLUMN period_start DATE')
            if 'period_end' not in schedule_columns: connection.exec_driver_sql('ALTER TABLE schedules ADD COLUMN period_end DATE')
            if 'time_from' not in schedule_columns: connection.exec_driver_sql('ALTER TABLE schedules ADD COLUMN time_from TIME')
            if 'time_to' not in schedule_columns: connection.exec_driver_sql('ALTER TABLE schedules ADD COLUMN time_to TIME')
            if 'instructor_name' not in schedule_columns: connection.exec_driver_sql('ALTER TABLE schedules ADD COLUMN instructor_name VARCHAR(160)')
    # Creates the roles and initial Super Admin only when they do not exist.
    # It is idempotent, so it is also safe on each local startup.
    seed()

# Serve the Vite single-page application after all API routes are registered.
# This keeps /api/v1, /docs, and /health available while supporting client routes.
dist_dir = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if dist_dir.is_dir():
    app.mount('/assets', StaticFiles(directory=dist_dir / 'assets'), name='assets')
    @app.get('/{client_path:path}', include_in_schema=False)
    def serve_frontend(client_path: str):
        requested = dist_dir / client_path
        if client_path and requested.is_file() and requested.resolve().is_relative_to(dist_dir.resolve()):
            return FileResponse(requested)
        return FileResponse(dist_dir / 'index.html')

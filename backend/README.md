# BDU-BIT LWMS API

Backend API for the BDU-BIT Laboratory and Workshop Management System.

## Run locally

1. Create and activate the virtual environment.
   ```powershell
   python -m venv venv
   .\venv\Scripts\pip install -r requirements.txt
   ```

2. Apply migrations.
   ```powershell
   .\venv\Scripts\python.exe -m alembic upgrade head
   ```

3. Reset and seed local demo data.
   ```powershell
   .\venv\Scripts\python.exe -m app.reset_dev_data
   ```

4. Start the API.
   ```powershell
   .\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
   ```

OpenAPI is served at `/docs`.

## Demo data

The reset command clears the local database and loads realistic BDU-BIT data for Mechanical Engineering and Electrical Engineering:

- 1 Dean
- 1 Coordinator
- 6 assigned facility assistants
- 3 maintainers
- 6 laboratories/workshops
- 12 resource groups with serialized equipment units
- project requests in pending, approved, and rejected states
- class and project schedules, including archived entries
- usage requests and maintenance cases with fixed, not fixed, pending, assigned, and in-progress states
- audit records showing which sample user performed each action

Demo login accounts are documented in `../docs/DEMO_CREDENTIALS.md`.

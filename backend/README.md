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
# Materials Store

The materials store is independent of laboratory and workshop equipment, but shares the LWMS login. The coordinator first creates a store and records each consumable (አላቂ) or durable (ቋሚ) material **with its quantity and purchase reference in that store**. Only then can the coordinator assign a store man. The store man checks every recorded delivery on a handover checklist and accepts the inventory, or reports a discrepancy. The store man cannot record stock. Later coordinator-recorded deliveries are checked separately. A store appears on the public request form only after its inventory handover is accepted, and only accepted stock can be issued.

Non-login requesters use `/store/request` and track status by a random `WS-...` reference. Consumable requests from staff go to their selected chair then dean; requests identified as chair go to dean; requests identified as dean go to coordinator so they cannot approve themselves. Dean confirmation records and forwards the request to the store man assigned to the requested store. The store man sees approved consumables, verifies the signed and sealed original, and records issue; that transaction reduces available stock and records the actor, request reference, material, quantity, and source delivery lot. If the store man changes before issue, the pending approved request is reassigned and the change is recorded. The prepared request form can be printed immediately. Uploading a signed copy is optional. Requester positions are self-declared on the public form, so the approving official must verify identity before approving.

The coordinator can grant or remove Chair request access for any existing account in People & Roles without replacing that account's other roles. Chair-only accounts see only requests addressed to them and can confirm and forward them to the dean; they cannot access store stock, handovers, or reports. A person who also holds the dean role cannot approve a request they personally confirmed as chair.

Durable materials need no approval form. The store man lends them directly, records a due date, and records partial or full returns. The Store Report shows on-hand quantities, receipts, issues, returns, outstanding loans, overdue loans, request states, and pageable actor-stamped movements. Store men see only their assigned stores; the dean can view all stores or filter to one. Every issue and return is linked to its source delivery lot.

Apply migrations through `0020_store_request_assignment` with `python -m alembic upgrade head` from `backend`. Legacy facility-bound stock is migrated to a separate unassigned store and must be assigned and accepted before new issues. SQLite development startup creates missing tables, but migrations are still required for existing databases.

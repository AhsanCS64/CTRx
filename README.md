# CTRx — Central Tenant Records

## Prerequisites
- Python 3.12+
- Node 20+
- PostgreSQL (the fresh container schema is validated on 18; database `ctrx`, role `ctrx_app`)
- WeasyPrint system libraries (libpango, libcairo) for PDF generation

## Setup & Run Order
1. Initialize an empty database from the reviewed base schema, then apply Alembic migrations (see [DOCKER.md](DOCKER.md)); existing databases retain their schema and migration history.
2. Configure `backend/.env` with the database URL and secrets using `backend/.env.example`.
3. Install backend dependencies with `cd backend; python -m pip install -r requirements.txt`.
4. Seed optional demo data with `python -m app.scripts.seed`.
5. Start the local API from `backend`: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8003 --reload`.
6. In a second terminal, run the UI: `cd frontend; npm ci; npm run dev` (port 5177; `/api` proxies to 8003).

The local API health check is `http://127.0.0.1:8003/health`; inspect `db: 1`
for database connectivity. The complete production-image Docker workflow,
optional isolated PostgreSQL, explicit bootstrap/migration commands and validation
limits are documented in [DOCKER.md](DOCKER.md). Docker does not change the
existing Vite/venv or Vercel/Render/Neon deployments.

## Environment Variables (.env)
```
DATABASE_URL=
TEST_DATABASE_URL=
JWT_SECRET_KEY=
HMAC_SECRET=
ENCRYPTION_KEY=
CORS_ORIGINS=
SEED_PASSWORD=
RUN_SCHEDULER= (optional)
```

## Smoke-Test Checklist (per role)
### Admin
- Login as admin@ctrx.test
- Create a government official
- Update a system setting
- View audit log
### Central Official
- Login as central@ctrx.test
- Review and approve an RIC application
- View issued certificate, revoke it, regenerate PDF
### Local Official
- Login as local1@ctrx.test
- Review queue shows only own area's applications
- Forward or reject an application
### Tenant
- Register, login
- Submit RIC application
- Search properties, create viewing request
- Accept payment request, view ledger
- Create access grant, view reliability score
### Landlord
- Register, login
- Create property with amenities
- Publish listing, respond to viewing requests
- Create tenancy, create payment request
- Record missed payment, add correction

## Issuance Flow
1. Tenant submits RIC application via /tenant/ric
2. Local official forwards via /government/review/:id
3. Central official approves via /government/review/:id
4. Household + members created; certificate issued; PDF rendered
5. QR code on PDF links to /verify/:token
6. Anyone can verify at GET /api/verify/:token (rate-limited: 30/min per IP)

## Certificate Template
The certificate design is a placeholder (version: v1-placeholder). To swap:
1. Implement a new class inheriting `CertificateRenderer` in `backend/app/certificates/renderer.py`
2. Create a new template version via POST /api/admin/templates/
3. Set it as default via POST /api/admin/templates/{id}/set-default
4. Update the renderer instantiation in `certificate_issuance.py`

## Background Jobs
```bash
python -m app.jobs.run expire_viewings    # marks stale viewing requests as expired
python -m app.jobs.run retry_pdfs         # retries PDF generation for pending certificates
```
Set `RUN_SCHEDULER=true` in .env to run both jobs automatically on a schedule.

## Running Tests
```bash
make test   # runs pytest against TEST_DATABASE_URL + frontend Jest
```
Test patterns:
- Normal tests: use rolled-back SAVEPOINTs (no persistent data)
- Concurrency tests: use UUID-based unique data; rows persist in the disposable test DB

## Decisions & Gaps
| Item | Decision |
|------|----------|
| No notifications table | NotificationService uses structured logging + audit entries (FR-75) |
| Stateless refresh tokens | No revocation list; acceptable for MVP |
| Login required before RIC application | Enforces identity linkage |
| Placeholder reliability formula | `score = clamp(50 + sum(deltas), 0, 100)` — clearly marked TODO |
| Per-process rate limiter | In-memory; not shared across processes; documented |
| No member add/remove outside applications | Household membership only via RIC workflow |
| PDF template is placeholder | Swappable via CertificateRenderer interface |
| Tenancy overlap checked in app layer | DB exclusion constraint not added; handled via SELECT + 409 |
```

# CTRx — Central Tenant Records

## Prerequisites
- Python 3.12+
- Node 20+
- PostgreSQL 17 (database `ctrx`, role `ctrx_app`)
- WeasyPrint system libraries (libpango, libcairo) for PDF generation

## Setup & Run Order
1. Apply `ctrx_schema_v0.3.sql` to the `ctrx` database as `ctrx_app`.
2. Configure `ctrx/.env` with the database URL and production secrets.
3. Install backend dependencies with `cd ctrx; poetry install`.
4. Seed optional demo data with `python -m app.scripts.seed`.
5. Start the API from `ctrx`: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.
6. In a second terminal, run the UI: `cd frontend; npm install; npm run dev -- --host 0.0.0.0`.

The API health check is `http://127.0.0.1:8000/health`; the minimal UI displays
both API and PostgreSQL status. For deployment, configure the secrets in the
environment and run `docker compose up --build`; place it behind an HTTPS
reverse proxy and use a hosted PostgreSQL instance.

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
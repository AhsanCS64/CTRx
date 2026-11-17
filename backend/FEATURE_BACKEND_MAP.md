# CTRx Backend Feature Map

This document maps the user-facing features to their API routes, implementation
modules, and persistent data. API routes below are mounted under `/api`.

## Request path

```text
React UI
  -> app/main.py (FastAPI, CORS, /api router mount)
  -> app/api/routers/<feature>.py (HTTP validation, role checks)
  -> app/schemas/ (request and response contracts)
  -> app/services/ (shared business rules, where present)
  -> app/db/models/ + PostgreSQL
```

`app/api/routers/__init__.py` is the router registry. A router file is not
available to the application unless it is listed there. Authenticated routes
use dependencies in `app/api/deps.py`; the database session is provided by
`app/db/session.py`.

## Fast pickup guide

For an existing feature, start with these files rather than searching the whole
repository:

1. `frontend/src/App.tsx` — API calls, workspace state and UI panels; several
   features share this large file.
2. `backend/app/api/routers/<feature>.py` — route, role check and response model.
3. `backend/app/schemas/<feature>.py` — request/response contract.
4. `backend/app/services/<feature>.py` — business rules and transaction handling.
5. `backend/app/db/models/<table>.py` and PostgreSQL schema — ORM mapping and
   persisted fields.
6. `backend/alembic/versions/` — database changes. Check `alembic heads` and
   use revision IDs (not filenames) for `down_revision`.

Keep authorization in the backend even when the UI hides an action. Preserve
historical RIC, tenancy and ledger data; use state transitions or new records
instead of deleting history. A browser CORS error can mask a backend 500; check
the API response and backend log before changing CORS configuration.

## Feature map

| Feature | API | Main implementation | Stored records / flow |
|---|---|---|---|
| Sign up, sign in, password reset, session | `/auth/*` | `api/routers/auth.py`, `services/auth.py`, `services/password_reset.py` | `users`, `password_reset_tokens`; email reset links are single-use and expire. The interview-demo endpoint changes a password by email alone and is enabled by default for the disposable demo. |
| Profile settings | `GET/PUT /profile`, `PUT /profile/appearance`, `PUT/DELETE /profile/photo` | `api/routers/profile.py`, `db/models/account_profiles.py` | All roles can edit their workspace display name, encrypted private contact number, photo, accent theme and light/dark preference. Photos are re-encoded as square JPEGs. |
| Tenant RIC application | `/ric_applications`, `/ric_applications/mine`, `/ric_applications/{id}` | `api/routers/ric_applications.py`, `services/ric_application.py` | `ric_applications`, `households`, `application_members`; identity number is encrypted and HMAC-indexed by the service. |
| Tenant relocation | `POST /ric_applications/relocate` | `api/routers/ric_applications.py`, `services/ric_application.py` | Creates a new RIC application for the new area and links it to the previous one; it does not overwrite the old application. Discovery uses the latest application area. |
| Government review | `/government/queue`, `/government/review/{id}` | `api/routers/government.py`, `services/government_review.py` | Role/official-level scoped review of `ric_applications`; local officials forward/reject, central officials approve/reject or return for local verification. Rejections and returns require written reasons and are audited. |
| Government dashboard | `GET /government/overview` | `api/routers/government.py` | Returns the signed-in official's level and assignment plus status counts and certificate totals, scoped to the assigned area for local officials and nationwide for central officials. |
| Certificates and verification | `/certificates/*`, `/verify/{token}` | `api/routers/certificates.py`, `services/certificate_issuance.py`, `api/routers/verification.py` | `rental_identity_certificates`, `certificate_documents`, templates; PDF data is returned for browser download and public verification uses a token. |
| Landlord buildings and apartments | `/properties/*` | `api/routers/properties.py` | `properties` is the building; `property_units` stores its apartments; landlords own both through `landlord_id`. |
| Rental listings and tenant search | `/properties/{id}/listing`, `/properties/units/{id}/listing`, `/properties/available-listings` | `api/routers/properties.py` | `listings` references a building and optionally a unit. Available listings may be filtered by `area_id`. |
| Viewing requests | `/viewings`, `/viewings/mine`, `/viewings/landlord`, `/viewings/{id}/status` | `api/routers/viewings.py` | `viewing_requests`; tenant proposes a time, listing owner confirms or declines. The database prevents duplicate requests for the same tenant/listing. |
| Rental offers / negotiation | `/rental_offers`, `/rental_offers/mine`, `/rental_offers/landlord`, `/rental_offers/{id}/respond`, `/rental_offers/{id}/tenant-respond` | `api/routers/rental_offers.py` | `rental_offers`; tenant offers rent, landlord accepts/rejects/counters, tenant may answer a counter or withdraw. Accepting creates a tenancy and marks the listing rented. |
| Tenancy history / move-out | `/tenancies/mine`, `/tenancies/{id}/status` | `api/routers/tenancies.py` | `tenancies`; generated when a rental offer is accepted. Ending a tenancy preserves the row and its rental history. |
| Monthly rent | `/rent/overview`, `/rent/tenancies`, `/rent/{tenancy_id}/invoice`, `/rent/invoices/{id}/pay`, `/rent/invoices/{id}/confirm`, `/rent/history` | `api/routers/rent.py`, `services/payments.py` | A rent invoice is a `payment_requests` row for a tenancy/month. Tenant reporting changes it to `submitted`; only the owning landlord can confirm it, which adds an append-only `ledger_entries` row. |
| General payments and ledger | `/payments/payment-requests/*`, `/payments/ledger/*` | `api/routers/payments.py`, `services/payments.py` | Tenant reports cannot mark money received; the landlord confirms receipt before a ledger row is created. Ledger rows cannot be updated or deleted. |
| Rental disputes | `/records/cases/*` | `api/routers/rental_records.py` | `disputes` and `dispute_timeline`; both tenancy parties can participate. Central officials and administrators can change case status. The timeline supports evidence and inbox updates. |
| Lease agreements | `/records/leases/*` | `api/routers/rental_records.py`, `20261122_rental_documents` | `lease_agreements` stores a snapshot of terms and each party's acknowledgement. New tenancies generate a draft. Older tenancies can prepare one from the workspace. |
| Rent statements | `/records/statements/*` | `api/routers/rental_records.py` | The selected tenancy and rent period scope posted ledger entries, corrections and pending invoices. Both parties can download a statement PDF. |
| Administration | `/admin/*` | `api/routers/admin.py`, `services/admin.py` | User/official provisioning, areas, settings, certificate templates and audit-log access. |
| Background processing | `app/jobs/*` | `jobs/run.py` | Optional scheduler expires stale viewings and retries PDF work when `RUN_SCHEDULER=true`. |

## SRS coverage

This table links the feature map to the functional requirements in
[SRS v1.1](../SRS.txt). **Present** means the main backend flow is visible
in the code. **Partial** identifies a specific gap or a requirement that
still needs checking. **No exposed workflow** means the router registry
has no dedicated API for that capability. These are source-review statuses.
Use integration tests to verify permissions, edge cases and deployment behavior.

| Feature | SRS requirements | Status and follow-up |
|---|---|---|
| Accounts and roles | FR-01–04 | **Present.** Registration, authentication and role-scoped routes are available. |
| RIC submission and evidence | FR-05, FR-70 | **Partial.** Submission requires an account. Verify supporting document storage, type metadata and checksums. |
| Government review | FR-06–08, FR-60–63 | **Partial.** Local and central review are implemented. Verify every required transition, rejection reason and rejected-application resubmission path. |
| Issuance, PDFs and public verification | FR-09–13, FR-64–68 | **Present.** Issuance, PDF generation and public token verification have backend paths. Verify numbering, expiry and revocation, the public response fields, PDF version metadata and scheduled retries. |
| Household and tenant records | FR-14–19, FR-26–28, FR-69 | **Partial.** Household applications, relocation and rental history have backend paths. Verify when old membership ends and how approval creates person records for members without accounts. |
| Previous RIC and prefilling | FR-20–25 | **Partial.** Relocation links to an earlier application. Verify the previous-RIC entry and prefill workflow, including active membership, identity-hash matching and rejection of revoked certificates. |
| Properties and listings | FR-29–33, FR-73 | **Present.** Landlords can create, edit, publish and withdraw listings. Tenants can filter by area and monthly rent. Units can have separate live listings. |
| Rental offers and tenancies | FR-34–37, FR-71 | **Present.** Offer acceptance creates a tenancy and move-out preserves history. Verify that concurrent acceptances cannot create overlapping tenancies for the same rentable space. |
| Payments and ledger | FR-38–42 | **Partial.** Requests, payment reports, landlord confirmation and ledger history are available. Clarify FR-39 and FR-40 so they describe both parties’ decisions and specify landlord confirmation as the point that creates the ledger entry. Verify correction entries against FR-42 separately. |
| Reliability scoring | FR-43–47 | **Partial.** Confirmed on-time and late payments, ledger corrections, and landlord-recorded missed rent generate explainable score changes. Missed-rent events are stored with append-only score snapshots. |
| Controlled sharing | FR-48–50 | **Present.** Tenants grant and revoke category-level access, and the landlord read endpoint checks the recipient and expiration. The UI selects landlords from the tenant's tenancy records. |
| Viewing requests | FR-51–53, FR-72 | **Present.** Landlords can propose a different time and tenants can accept or decline. Lists show timed-out requests as expired, the scheduler persists expiry, and a new request can replace a closed one. |
| Disputes | FR-54–56, FR-74 | **Present.** Submission, retrieval and review routes are available. Verify authorization and coverage for each reference type in FR-74. |
| Audit and administration | FR-57–59 | **Present.** Audit-log access and settings management have backend paths. Verify audit coverage and that the certificate validity period and verification URL settings are used by issuance. |
| Notifications | FR-75–76 | **Present.** The inbox persists RIC progress, payment changes, viewing responses, sharing activity and rental dispute updates. Email and SMS are optional channels under FR-76. |

### Workspace APIs

| Workflow | Routes and data |
|---|---|
| Inbox | `GET /workspace/notifications`, `POST /workspace/notifications/{id}/read`. Database triggers write RIC, payment and viewing notifications in the same transaction as each change. Sharing actions write notifications in their own transaction. |
| Sharing | `GET/POST /workspace/sharing`, `DELETE /workspace/sharing/{id}`, `GET /workspace/sharing/{id}/history`. `rental_history_grants` records recipient, categories, expiry and revocation. |
| Reliability | `GET /workspace/reliability` derives a score and explanation from the append-only ledger. The starting score is 50 after a first verified payment. An on-time payment adds 2 points, a late payment deducts 1, and a correction that crosses a zero balance reverses or restores the payment's effect. The displayed score is bounded to 0–100. |
| Listing management | `PATCH /properties/listings/{id}` edits, publishes or withdraws a live listing. Discovery accepts `area_id`, `min_rent` and `max_rent`. Each apartment can have its own live listing. A whole-building listing and individual apartment listings cannot be created concurrently for the same building. |
| Viewing rescheduling | `POST /viewings/{id}/status` accepts a landlord's `countered` action with an `alternative_time`. The tenant who opened the request can confirm or decline the counter-proposal. |

## Rent payment handoff

### State and permissions

```text
pending invoice
  -> submitted (tenant reports payment; no ledger entry)
  -> accepted (owning landlord confirms receipt; ledger entry created)
```

`payment_requests.status` uses PostgreSQL enum `payment_status`. Migration
`20261118_payment_confirmation` adds `submitted` and updates the
`guard_payment_request()` trigger. The tenant-facing generic
`POST /payments/payment-requests/{id}/decide` with `decision: "accepted"` also
means **report payment**; it must not accept the request or write the ledger.
Only landlord confirmation records payment as received.

| Action | Route | Enforcement / effect |
|---|---|---|
| Raise invoice | `POST /rent/{tenancy_id}/invoice` | Landlord must own an active tenancy; existing invoice is reused per tenancy/month. |
| Report payment | `POST /rent/invoices/{invoice_id}/pay` | Body: required `payment_method`, optional `note` and `paid_on`. Tenant must own the tenancy; future dates are rejected. Sets `submitted`. |
| Review reports | `GET /rent/tenancies` | Returns active tenancies with current-month invoice and submitted payment details. |
| Confirm receipt | `POST /rent/invoices/{invoice_id}/confirm` or `POST /payments/payment-requests/{request_id}/confirm` | Landlord must own the tenancy and request must be `submitted`; atomically sets `accepted` and inserts one append-only ledger row. |
| Tenant summary | `GET /rent/overview` | Paid state/totals come from ledger entries; a submitted report remains outstanding. |

Implementation pointers:

- Frontend calls and panels: `frontend/src/App.tsx` (`payRent`,
  `confirmRentPayment`, `TenantRentPanel`, `LandlordRentPanel`).
- Routes and response mapping: `backend/app/api/routers/rent.py` and
  `backend/app/api/routers/payments.py`.
- State transitions and ledger insertion:
  `backend/app/services/payments.py` (`submit_payment_report`,
  `confirm_payment_receipt`).
- Contracts and enum: `backend/app/schemas/rent.py`,
  `backend/app/schemas/payments.py`,
  `backend/app/db/models/payment_requests.py`.
- Focused regression tests: `backend/tests/test_payment_confirmation.py`.

There is currently no landlord reject/resubmit action for a submitted report.
Do not treat a tenant report as proof of receipt; only landlord confirmation
marks it paid.

## Monthly rent lifecycle

1. A landlord publishes a listing and a tenant submits a rental offer.
2. The landlord accepts (or the tenant accepts a landlord counter-offer).
   The offer handler creates an active tenancy.
3. The landlord opens **Rent** and calls `POST /rent/{tenancy_id}/invoice`.
   The API checks tenancy ownership/status and creates at most one invoice for
   that tenancy and billing month.
4. The tenant opens **Rent**. `GET /rent/overview` returns the active home,
   month, invoice and ledger totals.
5. `POST /rent/invoices/{invoice_id}/pay` verifies that the invoice belongs to
   the tenant and is pending. It records the tenant's payment method/reference
   and changes the request to `submitted`, without creating a ledger row.
6. The landlord reviews the report in **Rent**. `POST
   /rent/invoices/{invoice_id}/confirm` checks ownership, marks the request
   accepted and inserts the payment ledger entry atomically. Until then, the
   tenant sees that confirmation is pending and the balance remains outstanding.
7. The tenant and landlord can refresh their rent views; invoice state comes
   from `payment_requests`, and paid history comes from `ledger_entries`.

## Important database mappings

The ORM attribute names intentionally differ from some deployed database column
names. Preserve these mappings when changing models:

| Python attribute | PostgreSQL column |
|---|---|
| `Tenancy.rent` | `tenancies.monthly_rent` |
| `PaymentRequest.created_at` | `payment_requests.submitted_at` |
| `LedgerEntry.created_by` | `ledger_entries.actor_id` |
| `LedgerEntry.correction_reason` | `ledger_entries.reason` |
| `ViewingRequest.updated_at` | `viewing_requests.responded_at` |

`payment_requests.paid_on` and `ledger_entries.paid_on` are required by the
database. Rent billing sets the requested due date; a tenant report records the
claimed payment date, which is copied to the ledger only after landlord
confirmation. Ledger entries are append-only, so corrections are new entries
rather than edits.

## Local validation

From PowerShell:

```powershell
Set-Location 'K:\Personal Projects\CTRx\backend'
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\python.exe -m pytest tests\test_payment_confirmation.py -q
.\.venv\Scripts\python.exe -m compileall -q app tests

Set-Location 'K:\Personal Projects\CTRx\frontend'
npm.cmd run build
```

Run `.\.venv\Scripts\alembic.exe upgrade head` only when the local database
needs unapplied migrations. The frontend API defaults to port `8003`; an
explicit `VITE_API_BASE_URL` overrides it.

## Current boundaries

- Rental dispute workspaces cover tenancy and payment-request cases.
- Reliability history combines confirmed ledger entries and documented missed rent. A confirmed payment clears the missed-rent penalty for the same tenancy and period.
- Lease acknowledgements record each party's acceptance of a snapshot.
- The redesigned RIC PDF registers a new document version under
  `ctrx-ric-v3` while retaining the certificate number, QR token and dates.
- Existing properties/listings and historical RIC/tenancy records should be
  retained; lifecycle changes should add or transition records, not erase
  history.
- Support tickets use the existing `support_tickets` and
  `support_ticket_messages` tables through `/api/support/tickets`.
- `/api/workspace/privacy` displays the tenant's history grants and consent
  events. `/api/workspace/reliability/events` exposes recorded score events.
- Certificate download activity is recorded in
  `certificate_delivery_events` and displayed in Records & privacy.


## Full application handoff

This section supplements the earlier tables with the current cross-layer behavior.
Use the implementation and installed schema to resolve older descriptions.

### Frontend entry points

frontend/src/main.tsx mounts App.tsx. CSS loads in this order: styles.css,
presentation.css, landing.css. App.tsx owns authentication, the fetch/refresh
helper, workspace state, role navigation and most domain panels. Its workspace
key selects a rendered screen. The pages directory is older scaffolding and is
not the primary application entry point.

| Feature | Frontend source | Backend source under app |
| --- | --- | --- |
| Rent, tenancies and listings | App.tsx | api/routers/rent.py, tenancies.py, properties.py |
| Offer negotiation | App.tsx | api/routers/rental_offers.py |
| Leases, statements, disputes, evidence | RentalRecords.tsx | api/routers/rental_records.py |
| Inspections, repairs, deposits | TenancyCare.tsx | api/routers/tenancy_care.py |
| Monthly two-way feedback | TenancyFeedback.tsx | api/routers/tenancies.py |
| Reliability and controlled sharing | App.tsx, TrustHistory.tsx | services/scoring.py, api/routers/workspace.py |
| Public 24-hour identity verification | RentalIdentityShare.tsx | api/routers/rental_identity_sharing.py |
| Excel exports | ExportPanel.tsx, workbookExport.ts, dataset definitions in App.tsx | Existing role-scoped endpoints |
| Profile and themes | App.tsx, presentation.css | api/routers/profile.py, db/models/account_profiles.py |
| Workspace search | WorkspaceSearch.tsx | Already authorized loaded records |

Inbox keyword search and All/Unread filters cover the latest 100 notifications
returned by the API. Command search uses loaded scoped records. The language
switch provides partial Bangla localization of header and navigation.
Excel exports generate XLSX in the browser, with selected sheets, numeric BDT
amounts, literal strings, frozen headers and filters. Rental exports include
party names, residence address and apartment.

### Building and apartment identity

properties represents buildings or whole-property rentals. property_units
represents apartments. listings.unit_id identifies the advertised apartment;
tenancies.unit_id persists the rented apartment. Accepted offers create linked
tenancies. Migration 20261201_tenancy_apartment backfills older records only when
accepted offers identify an unambiguous unit. Unresolved legacy tenancies have a
null unit and reserve the property.

Vacancy checks apply during listing creation, editing, discovery and offer
acceptance. One rented apartment leaves other apartments eligible. A database
exclusion constraint prevents overlapping active tenancies for the same apartment.
API checks also respect legacy whole-property tenancies.
Apartment numbers appear in rent, tenancy selectors, leases, statements, receipts,
feedback, tenancy care, offers, listings and Excel exports.

Lease terms are stored as a snapshot in lease_agreements. An account-specific
historical Niribili Apartment 5-Ka lease correction already exists in the database.
Do not turn that correction into generic seed logic. Financial history is retained
when a tenancy is ended or terminated.

### Dates, feedback and reliability

Date corrections live in Lease agreements → Tenancy details. A landlord can
correct an unacknowledged draft. Acknowledged leases require a landlord proposal
and tenant approval. Audit history retains previous terms and acknowledgements.
The API validates dates, overlap and existing rent/feedback records. Notifications
link to the lease. Feedback only links to tenancy details when the date blocks review.

monthly_tenancy_feedback stores one rating per tenancy, author, month and category.
Both parties review the other party. Categories include communication, rent
handling, property care, repairs and conduct. Future months and months outside the
tenancy are rejected. tenancy_feedback holds older undated remarks.

services/scoring.py is the shared live calculation for Reliability, score history,
controlled sharing and public verification. Scores recalculate on read from records.

- Baseline 50 with qualifying history, bounded to 0–100.
- Confirmed on-time payments add 2; confirmed late payments subtract 1.
- The deadline is the latest of rent due day, tenancy start and invoice issue date,
  capped at the billed month's end. Following-month payments are late. Invoice
  timestamps and payment reporting use Dhaka dates.
- Landlords explicitly record overdue, unreported rent as missed, subtracting 3.
  Append-only score events/snapshots prevent duplicate missed events for a period.
  The tenant receives a notification.
- A net-positive confirmed payment clears the same tenancy/month missed penalty.
  Ledger corrections adjust the original event without rewriting it. Fully reversed
  payments alone leave no qualifying score history.
- Positive monthly landlord feedback adds at most 1 per tenant/calendar month when
  no concern is recorded for that month. More categories or repeated edits do not
  stack points. Tenant feedback about landlords does not affect the tenant score.
- Marital status, living arrangement and uploaded documents do not affect the score.

Ledger and stored scoring history are append-only. Fix the shared calculation or
running backend version instead of changing historical payment rows to repair a label.
The app reports a payment before landlord confirmation; confirmation posts the ledger
entry and enables a receipt. There is no live bKash/Nagad webhook integration.

### Profiles and presentation

Optional marital status and living arrangement are private account_profiles fields.
Profile photos use normalized files under STORAGE_DIR, media_files metadata and
active photos associations, with a legacy fallback.
Themes are Jade, Harbor, Graphite and Comfort. Comfort is Warm Paper in light mode
and Midnight Forest in dark mode. Legacy names map into this lineup. Theme changes
use the profile appearance endpoint. Semantic badges keep success/warning/error colors.
The four-circle RIC tracker distinguishes approval from certificate issuance and
opens recorded milestone details. Motion respects reduced-motion preferences.

### Runtime and deployment

app/core/config.py owns settings. DATABASE_URL, TEST_DATABASE_URL, JWT_SECRET_KEY,
HMAC_SECRET and ENCRYPTION_KEY are currently required when importing the app.
Keep secrets outside images and source control; preserve the encryption key for
existing encrypted data. CORS_ORIGINS is a JSON array. STORAGE_DIR needs persistent
storage for uploaded media and generated documents. Public frontend and verification
URLs determine external links. Password reset supports Resend or SMTP; the demo
password-reset endpoint is enabled by default via a separate flag.

/health reports API status and a database flag; inspect both for readiness.
Register routers in app/api/routers/__init__.py. Run Alembic explicitly with the
backend working directory and configured environment. Latest migration is
20261201_tenancy_apartment. The migration chain assumes a pre-existing base schema.
The schema-only ctrx.backup can initialize a fresh database after owner/extension
compatibility review. It contains no demo users.

Local Vite defaults to port 5177 with /api proxying to backend port 8003.
CTRX_DEV_API_TARGET can override the proxy in an ignored local environment file.
The browser API base uses VITE_API_BASE_URL or the browser origin. VITE variables
are bundled at build time. Internal container names belong in proxy upstreams,
not browser API URLs. Several development preview ports have been used; inspect
listeners and environment before launching more servers.

Hosted deployment uses Vercel, Render and Neon. Code commits, service deployments
and database migrations are separate. Confirm the deployed backend commit and
actual authenticated response when hosted behavior differs from local behavior.

### Dockerization starting point

Portable distribution uses `portable/compose.yml` without build contexts and
Windows Start/Stop launchers. `scripts/Export-Portable.ps1` packages existing
images with private `.env.docker` into ignored `CTRx-Portable/`. Startup performs
only the read-only schema check, never bootstrap/upgrade. Its separate project
`ctrx-portable` retains its media volume; media is not bundled automatically.

Implemented container workflow is documented in `../DOCKER.md`.

| Component | Implementation |
| --- | --- |
| Build contexts | Repository root for both Dockerfiles; root `.dockerignore` allowlists source, locks and Assets and excludes secrets/user data. Per-directory ignore files document the supported context. |
| API image | Python 3.12, runtime dependency pins in `requirements-docker.lock`, psycopg binary, Pillow, ReportLab and WeasyPrint 62.3/pydyf 0.10.0 plus native Pango/font dependencies; build-time native PDF check; UID/GID 10001. |
| Frontend image | `npm ci`, TypeScript check and Vite production build, served by unprivileged Nginx. Includes repository Assets during compilation. No Vite environment file is copied. |
| HTTP | Host loopback port 8080 to Nginx; `/api` and `/health` preserve paths through the backend proxy. SPA fallback excludes API and missing build assets. Docker DNS is re-resolved on backend replacement. |
| Configuration | Ignored `.env.docker`, public `.env.docker.example`; supports external PostgreSQL/Neon. Local/hosted environment files remain independent. |
| Persistence | Named `media` volume at `/app/storage` for normalized uploads and certificate PDFs. Optional `docker-compose.local.yml` adds PostgreSQL 18 and `pgdata`; no published DB port. |
| Schema management | Explicit `migrate` service runs `app.scripts.container_db upgrade`. API workers never migrate. Schema operations reject concurrency via a session advisory lock; use a direct provider connection. |
| Bootstrap | `container_db bootstrap` requires an empty public application schema, restores reviewed `docker/base-schema.sql` and records baseline `20261127_rent_confirmation` atomically. This schema-only snapshot was extracted from repository `ctrx.backup`, stripping owner/ACL directives and psql metacommands; it contains no user data. Run upgrade afterward. Never stamp an unknown existing database. |
| Readiness | Backend health requires HTTP `/health` with `db: 1` and exact Alembic head; frontend waits for backend health and has a static `/healthz` liveness check. |
| Smoke test | `app.scripts.container_smoke write --require-html-pdf` and `verify`, explicitly enabled only for local disposable data, cover HTTP/frontend assets, auth/refresh, authorization, image upload, native PDF generation and storage after recreation. |

From root, use `docker compose --env-file .env.docker build`; bootstrap only an
empty database using `run --rm migrate python -m app.scripts.container_db bootstrap`,
then `run --rm migrate`, seed areas if needed, and `up -d --wait backend frontend`.
Use `down` to stop without removing volumes. The runbook includes an isolated
local project and commands, migration, backup and troubleshooting procedures.

Validation: TypeScript check and Vite production build passed; 23 focused backend
tests passed. Local ReportLab certificate generation and PDF storage round-trip
passed, as did YAML parsing, Python compilation and dependency constraint checks.
The reviewed schema restored and remaining migration SQL executed
against a fresh isolated PostgreSQL 18 cluster, reaching the current head with
the apartment exclusion constraint and zero users. Single-user mode avoided
the environment's blocked loopback TCP. Docker and registry/package network
access were unavailable, so image builds, Compose/Nginx operation, authenticated
API-to-DB integration, native Linux rendering and volume recreation checks remain
unverified. No existing Neon database or Vercel/Render deployment was changed.

### Validation and next-agent workflow

Inspect Git status first. Read AGENTS.md, this map, the relevant router/service,
and its migrations. Confirm the actual frontend entry point and running API version.
Frontend checks are tsc --noEmit -p frontend/tsconfig.json and npm --prefix frontend
run build. Backend tests are under backend/tests; many use fake sessions, so they
do not replace PostgreSQL integration checks. TEST_DATABASE_URL is required by
current settings. Use isolated test data and avoid printing secrets.
The frontend npm test script currently calls itself recursively and is not a usable runner.
Verify normal UI entry points, authorization, API data shapes, and persistence
before completion. Update AGENTS.md and this map when behavior changes.

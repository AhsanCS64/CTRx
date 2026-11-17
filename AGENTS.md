# CTRx — Project implementation map

This file documents how the CTRx (Central Tenant Records) project is implemented
and how its features work in code. It is intended for future agentic coding
sessions — read it before making changes so you do not duplicate or break
existing behavior.

## Project layout

```
K:\Personal Projects\CTRx\
  backend/                 FastAPI + SQLAlchemy + Alembic + psycopg
    app/
      api/
        routers/*.py       One router per domain (mounted under /api)
      services/*.py        Business logic (payments, scoring, etc.)
      schemas/*.py         Pydantic request/response schemas
      db/
        models/*.py        SQLAlchemy 2.0 Mapped classes
        base.py            declarative Base
        session.py         engine + SessionLocal
      alembic/versions/    DB migrations
    alembic.ini
    pyproject.toml
  frontend/                Vite + React 18 (single-file App.tsx)
    src/
      App.tsx              Entire UI (routes, components, API helpers, types)
      styles.css           Design system + components CSS
      api/                 axios client helper files (client.ts, admin.ts, ...)
      pages/               Page components (login, register, admin, gov, public)
    index.html
    package.json
    vite.config.ts
AGENTS.md                  This file
```

## Tech stack

- Backend: FastAPI, SQLAlchemy 2.0 (async/sync), PostgreSQL + psycopg, Alembic
  for migrations, pydantic-settings for config, `argon2-cffi` for passwords,
  `python-jose` for JWT.
- Frontend: React 18, Vite, `axios`, raw `fetch` in `App.tsx`, plain CSS (no
  UI framework).
- Auth: bearer access token in `localStorage` + refresh endpoint
  `/api/auth/refresh`. `App.tsx.request()` auto-refreshes on 401.
- Password recovery uses `/api/auth/password-reset/request` and
  `/api/auth/password-reset/confirm`. Requests return the same message for
  existing and unknown addresses. Reset links are single-use and expire after
  `PASSWORD_RESET_EXPIRE_MINUTES` (20 by default). Hosted environments can use
  Resend's HTTPS API with `RESEND_API_KEY` and `EMAIL_FROM`; local development
  can use an SMTP inbox such as Mailpit at `localhost:1025`. Production reset
  links require the public HTTPS frontend URL.
- The interview demo enables `POST /api/auth/password-reset/demo` by default.
  It changes a password by email alone, so it is only suitable for disposable
  demo data and must be disabled before using real user accounts.

## How the app is wired

### Backend app factory (`backend/app/main.py`)
- `create_app()` loads settings, configures CORS, includes every router from
  `app/api/routers/__init__.py` under prefix `/api`, registers a global
  `ValueError` → 400 handler, and a `/health` check.
- `app/api/routers/__init__.py` imports each router module by string path and
  collects `router` into `ALL_ROUTERS`. **New routers must be added to that
  list** or they will never be mounted.

### Routing convention
- Every router file creates `router = APIRouter(prefix="/<domain>", ...)` and
  FastAPI includes it under `/api`, so final paths are `/api/<domain>/...`.
- All state-changing endpoints emit an audit log via `app/audit.py`.

### Frontend (`frontend/src/App.tsx`)
- `App.tsx` is a single file containing: types, the `request()` fetch helper,
  auth screens, the `Workspace` shell (sidebar + content), and every page
  component.
- Sidebar nav is built from a `nav: string[][]` array keyed by `workspace`
  (`['key', 'Label', 'iconName']`). Each key maps to a component rendered in
  `Workspace` via `{workspace === 'key' && <Component ... />}`.
- `request()` uses `apiBaseUrl = VITE_API_BASE_URL || 'http://127.0.0.1:8000'`
  and sends `Authorization: Bearer <access_token>`.

## Data model (key tables)

- `users(id, email, role, is_active, ...)` — roles: tenant, landlord,
  government, admin.
- `persons`, `tenant_profiles(user_id → users)`, `landlord_profiles`,
  `official_profiles`.
- `areas(id, division, district, name)`, `properties`, `property_units`,
  `listings(property_id, status, ...)`.
- `ric_applications`, `rental_identity_certificates`.
- `tenancies(property_id, tenant_id, landlord_id, rent, deposit,
  rent_due_day, status, ...)` — active/ended/terminated.
- `viewings/viewing_requests` and `rental_offers` (offer→counter→accept).
- `payment_requests(tenancy_id, amount, period_month, status)` and
  `ledger_entries(tenancy_id, entry_type, amount, period_month, ...)` —
  append-only ledger (DB triggers forbid UPDATE/DELETE).

## Authentication & authorization pattern

- `get_current_user` dependency resolves the bearer token to a `User`.
- Role helpers in routers: `_tenant(user)`, `_landlord(user)` raise 403.
- Data scoping bug fixed in `app/services/payments.py`: `get_payment_requests`
  and `get_ledger` now join `tenancies` so tenants only see their own tenancy
  data and landlords only see their own tenancies' data.

## Recently implemented features

### 1) Rental offers (`rental_offers`)
- `POST /api/rental_offers` — tenant makes an offer on an `available` listing
  (auto-creates tenant profile if missing; one open offer per tenant/listing via
  partial unique index; expires in 7 days).
- `GET /api/rental_offers/mine` — tenant's offers.
- `GET /api/rental_offers/landlord` — offers on the landlord's listings.
- `POST /api/rental_offers/{id}/respond` — landlord accept/reject/counter.
- `POST /api/rental_offers/{id}/tenant-respond` — tenant accept counter /
  counter back / withdraw.
- Accepted offers create a `tenancies` record and mark the listing `rented`.
- Frontend: tenant "My offers" + landlord "Rental offers" workspace pages.

### 2) Monthly rent system (`/rent`)
Built on `tenancies` + `payment_requests` + `ledger_entries`.
- `GET /api/rent/overview` (tenant) — current active tenancy, home address,
  rent, due day, current period, invoice status, total paid, outstanding.
- `GET /api/rent/tenancies` (landlord) — active tenancies with tenant name +
  current-period invoice state.
- `POST /api/rent/{tenancy_id}/invoice` (landlord) — raise this month's rent
  invoice (amount defaults to tenancy rent; idempotent per month).
- `POST /api/rent/invoices/{id}/pay` (tenant) — accept/pay a pending invoice,
  which records an append-only ledger entry.
- `GET /api/rent/history` — invoice history scoped to the caller's tenancies.
- Frontend: tenant "Rent" page (current home card + pay button), landlord "Rent"
  page (raise rent per tenancy), and a "Current home" panel on the tenant
  overview.

### Government dashboard
- `GET /api/government/overview` returns the signed-in official's level,
  assignment and RIC workflow counts. Local officials are scoped to their
  assigned area; central officials receive nationwide counts.
- The government overview uses those counts with the existing scoped review
  queue and certificate list. Tenant overview keeps application tracking and
  current rent information prominent.
- Central officials can reject a pending central review with a written reason,
  approve it, or return it to pending local review with written verification
  instructions. The return is area-scoped when it re-enters the local queue;
  the database trigger enforces the reviewer level and required note.

### Profile media and rent confirmation
- New profile avatars are normalized and stored as files under `STORAGE_DIR`;
  `media_files` stores file metadata and `photos` associates the active profile
  image with a user. `account_profiles.photo` remains a legacy read fallback.
- Migration `20261127_rent_confirmation` relaxes the payment-request maker/checker
  constraint only for accepted rent receipts with a recorded payment method.
  Apply it to the installed schema before enabling landlord rent confirmation.

## Design patterns used

- SQLAlchemy `Mapped[mapped_column]` style; migrations managed by Alembic (do
  **not** call `Base.metadata.create_all`).
- Ledger entries are append-only; never `db.delete()` them. IntegrityError with
  `forbid_mutation` → 409 `ERR_LEDGER_IMMUTABLE`; duplicate payment in ledger →
  409 `ERR_PAYMENT_ALREADY_IN_LEDGER`.
- Frontend components receive all data via props from `Workspace`; no context
  or state library. Loading states use a shared `busy` flag; errors/notices use
  `error`/`notice` alert banners.
- CSS design system: teal primary (`--teal-500`), amber accent, ink neutrals,
  radius/elevation/motion tokens, `.panel`, `.stat-card`, `.record-row`,
  `.status-*` badges, responsive stacking below ~900px.

## How to run

Backend:
```
cd backend
# needs .env with DATABASE_URL and secret settings
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Apply migrations (alembic must be installed in the venv):
```
cd backend
python -m alembic upgrade head
```
If alembic is unavailable, apply the equivalent DDL manually and stamp:
`UPDATE alembic_version SET version_num='<latest>'`.

Frontend:
```
cd frontend
npm run dev      # Vite dev server
npm run build    # production build
```

## Known caveats / limitations

- `rental_offers` status enum has an `expired` value but **no scheduled job
  flips offers to `expired`** — they stay `pending` until acted on or withdrawn.
- Payments "decide" uses `accept|reject|cancelled`; rent "pay" only uses
  `accepted`.
- The live backend on port 8000 can go stale if started without `--reload`;
  after code changes you must restart it so new routers/mounts load.

## Adding a new feature

1. Add model(s) under `backend/app/db/models/` and an Alembic migration under
   `backend/alembic/versions/`.
2. Add schema(s) under `backend/app/schemas/` and router under
   `backend/app/api/routers/`, then register the router module in
   `backend/app/api/routers/__init__.py`.
3. Add TypeScript types/state/handlers in `frontend/src/App.tsx`, register the
   workspace key in the `nav` array and render the component in `Workspace`.
4. Add CSS classes to `frontend/src/styles.css`; keep to the design tokens.
5. Update this file (`AGENTS.md`) when behavior changes.

## Post-move-in workspace

- `/api/tenancy-care` lists the caller's tenancies and their shared records. The
  `20261123_tenancy_care` migration adds tenancy-scoped storage.
- Both parties can file and acknowledge move-in and move-out inspections.
  Tenants report maintenance on active tenancies and landlords record dated
  repair updates. Completed work and ended tenancies retain their history.
- Landlords record settlements and returns after a tenancy ends. Tenants
  respond to individual deductions. Inspection and settlement records can
  be linked to an existing case for the same tenancy.
- `frontend/src/TenancyCare.tsx` and `RentalTools.tsx` provide the workspace
  screens. Tools include rent affordability, move-in budget, shared rent,
  and meter usage calculators. Account appearance also supports Rose, Forest,
  and Ocean in light and dark modes.

### Workspace presentation
Navigation is grouped by workflow, with profile settings in the top-right account control. Overview includes role-specific actions. Public aggregate counts are served by /api/public/statistics. The landing page includes the engineer photo from Assets/Developer/kushal.jpg. Tools include a session-only move checklist and repair-message drafting. Authentication screens have a prominent Back to home control and responsive introduction panel.

Landing sign-in roles are accessible from the header dropdown. The footer provides feature and engineer anchors, registration, and a back-to-top link. Profile appearance uses keyboard-accessible palette radio cards while retaining existing stored theme values.

Tools includes GeneralCalculator.tsx with left-to-right arithmetic, decimals, sign toggle, percentage conversion, clear/backspace, and keyboard controls. Percentage divides the displayed operand by 100.

The engineer section identifies H M AHSAN HABIB KUSHAL as AI/ML and Database Engineer and System Architect, with the supplied GitHub and portfolio links. Landing animations use bounded CSS transforms and opacity and respect prefers-reduced-motion.

Sidebar workflow sections are collapsible, with Workspace and the currently selected section expanded on navigation. Workspace surfaces and dark palettes use shared theme tokens. Desktop login and signup layouts were visually reviewed.


On phones and tablets, the workspace navigation opens as a scrollable drawer with a close button and Escape support. Narrow layouts let actions wrap and stack record facts and support panels.


The government overview includes a searchable worklist preview and a scoped application status breakdown. Central approval and certificate issuance require confirmation. Shared surfaces and KPI cards use palette-derived tokens.
`frontend/src/presentation.css` is loaded after the base styles and provides palette-aware presentation rules. The landing developer card lives in `frontend/src/EngineerProfile.tsx`.

The `areas` table is seeded from `backend/app/data/bangladesh_areas.json` using `python -m app.scripts.seed_areas`. It stores upazila/thana records with division and district codes; tenant applications, relocations, landlord properties, local official assignments, and tenant listing filters use cascading division → district → upazila selectors. Property and listing responses include the associated area, district, and division for clear location display.

The uploaded `ctrx.backup` is schema-only; it contains no account rows to restore. First-admin setup is a one-time bootstrap gated by the server's `SEED_PASSWORD`, and admin names are stored in `account_profiles.display_name`.
The full official review queue supports applicant or area search and a status filter over the scoped records already loaded.
Records & privacy shows an independent loading or retry state for privacy history and supports older consent records with missing scope values.
Workspace overview places tenant application and home records before recommended actions. Sharing panels and workspace forms stack at narrow widths.
Government overview places the review worklist before the workflow guide. Records & privacy appears in tenant and landlord navigation.

The public landing page uses scoped styles in frontend/src/landing.css for its navigation, rental identity introduction, feature grid, and registration actions.
The tenant overview links to application tracking or starts a new application, and offers PDF download when an active certificate is available. Current Home shows ledger-backed payment status and the total paid for the tenancy. The RIC stepper uses four responsive circles with connector bars and selectable milestone details. Sidebar navigation scrolls independently of the logout footer.
The workspace header groups the greeting and account controls in a padded card, with controls below the title on narrower screens.
Dark workspace text uses separate heading, body, and metadata tones, with palette accents for actions and semantic colors for alerts and review status.
Tenant Current Home shows the next due date for settled rent and opens payment reporting from urgent actionable invoices. Payment reporting supports named local transfer methods and still requires landlord confirmation. The RIC stepper uses recorded notes and timestamps, including linked certificate issuance. Workspace search uses already scoped records and the workspace header and navigation support বাংলা. Tenants can generate signed 24-hour public rental identity links that show the applicant name, certificate standing, and aggregate rental reliability.
Confirmed rent invoices provide an authenticated PDF receipt from the posted payment ledger entry.
The RIC progress tracker distinguishes returned review, rejection, approval pending issuance, and issued certificates. Select a milestone to view its recorded details in Dhaka time.
Inbox supports keyword search and an unread filter for the latest notifications returned by the workspace API. Exports builds a multi-sheet Excel workbook from role-scoped records and excludes private identity data and reviewer notes.
Excel exports include record-scoped tenant and landlord names, the saved residence address for rent and tenancy records, listing titles, and applicant or certificate-holder names where applicable.
Reliability combines confirmed ledger payments, corrections, and landlord-recorded missed invoices. Missed records are append-only, scoped to one tenancy and month, and stop affecting the live score if a confirmed payment covers that period. The tenant receives a notification. Apply the reliability and tenancy-feedback migrations before serving these endpoints.
Tenants and landlords can add or edit one structured assessment per category on their shared tenancy through My rental → Tenancy feedback. Feedback is visible only to parties on that tenancy. Monthly landlord feedback can affect the score under the rule below.
Tenancy feedback is month-specific. Positive landlord feedback with no concern in the same calendar month adds at most one reliability point per tenant. Earlier remarks remain readable without affecting the score. Optional marital status and living arrangement are private profile preferences and do not enter scoring or exports.
Landlords can correct a start date from Lease agreements → Tenancy details. The API updates any unacknowledged lease draft, audits the correction, notifies the tenant, and rejects conflicts with existing records, acknowledged terms, or database date constraints.
Start-date corrections are in Lease agreements → Tenancy details. Feedback links there when the tenancy has not started. Listing creation, publishing, searches, and offer acceptance respect apartment-level occupancy. Building-level legacy tenancies reserve the property.
For acknowledged leases, landlords propose a start-date correction and the tenant approves or declines it. The tenancy date changes only on approval, and the previous acknowledged terms remain recorded in the audit history.
Accepted apartment offers persist the unit on the tenancy. The apartment migration links older tenancies when a matching accepted offer identifies one unit. Lease details, rental documents, rent, feedback, tenancy care, and Excel exports show the unit where recorded.
Reliability caps the effective payment deadline at the end of the billed month. A payment in the following month is late even when an invoice or tenancy started after the usual due day.
Profile themes are Jade, Harbor, Graphite, and Comfort (Warm Paper in light mode and Midnight Forest in dark mode). Legacy saved palette names map to the curated lineup without a database migration.


## Agent handoff

### Container architecture

Portable Windows launchers and image-only Compose live in `portable/`.
`scripts/Export-Portable.ps1` exports existing images and private configuration
into ignored `CTRx-Portable/`. Launchers use project `ctrx-portable`, check schema
readiness without migrations, retain media on stop, and open the browser.
Media export is separate; see `portable/README.md`.

See `DOCKER.md` for setup and validation limits. Both Dockerfiles use repository
root build contexts. `docker-compose.yml` runs a non-root FastAPI image and a
production Vite build served by unprivileged Nginx on port 8080, with same-origin
`/api` and `/health` proxying. Repository `Assets` is included in both images.
Secrets live in ignored `.env.docker` (template `.env.docker.example`). Named
volume `media` mounts at `/app/storage`; optional `docker-compose.local.yml`
adds an isolated PostgreSQL 18 service and `pgdata` volume without a host DB port.

Commands from root: `docker compose --env-file .env.docker build`, then for an
empty database only, `docker compose --env-file .env.docker run --rm migrate
python -m app.scripts.container_db bootstrap`. The reviewed schema-only baseline
is `backend/docker/base-schema.sql`, at revision `20261127_rent_confirmation`;
bootstrap refuses existing application relations and records this revision
transactionally. Never bootstrap an existing deployment or stamp an unknown schema.
Run `docker compose --env-file .env.docker run --rm migrate`, optionally seed
areas with that service, then `docker compose --env-file .env.docker up -d --wait
backend frontend`. `down` retains volumes. API workers never migrate on startup.
Use a direct PostgreSQL connection for schema commands (session advisory lock).
Backend health checks database connectivity and migration head; frontend health
checks Nginx. `container_smoke` validates HTTP, auth, photos, PDFs and persistence
only against explicitly enabled disposable local databases; see the runbook.
Container Python pins are separate from local/hosted requirements. Alembic URL
configuration now supports percent-encoded passwords. Existing dev and hosted
workflows remain supported. Docker was unavailable during this change; frontend
build/type-check, 23 focused backend tests and isolated PostgreSQL schema/migration
SQL passed. Full Linux container integration remains to be run.

Read backend/FEATURE_BACKEND_MAP.md for the current full application map and
Dockerization starting points. Its latest handoff section covers frontend entry
points, apartment identity, scoring, profiles, deployment and validation.
Latest migration in this checkout is 20261201_tenancy_apartment. Alembic assumes
an existing base schema. Inspect actual environment settings and service versions
before diagnosing issues, because local and hosted deployments can differ.

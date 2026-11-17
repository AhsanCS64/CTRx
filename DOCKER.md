# CTRx containers

## Portable Windows package

After building and verifying the images, run
`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Export-Portable.ps1`
from the repository root. Carry the generated, Git-ignored `CTRx-Portable` folder.
It contains image archives and private runtime credentials. On a compatible PC,
open Docker Desktop (Linux containers) and double-click `Start-CTRx.cmd`;
`Stop-CTRx.cmd` retains the media volume. See `portable/README.md` for limitations
and updating images. No migrations run automatically. The portable project has
its own media volume; existing media is not included in the export.

Run commands from the repository root in PowerShell. Requires Docker Engine/Desktop
with Linux containers and Compose v2. Nothing here replaces the existing Vite,
Python venv, Vercel, Render or Neon workflows.

## Configure and build

```powershell
Copy-Item .env.docker.example .env.docker
# Edit .env.docker before continuing.
function dc { docker compose --env-file .env.docker @args }
dc build
```

Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL (`postgresql+psycopg://...`).
Neon works with `?sslmode=require`. URL-encode password characters, including `%`,
`@`, `/` and `#`. Containers cannot reach the host through `localhost`; use
`host.docker.internal` for a host database on Docker Desktop. Keep
`TEST_DATABASE_URL` on a separate disposable database; the application currently
requires it even when not testing.

Generate independent JWT/HMAC secrets and a Fernet encryption key, for example:

```powershell
docker run --rm python:3.12.8-slim-bookworm python -c "import secrets; print(secrets.token_urlsafe(48))"
docker run --rm python:3.12.8-slim-bookworm python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

The second command produces a Fernet key. Preserve the existing encryption and
HMAC keys when connecting existing encrypted records. Set `SEED_PASSWORD` only
when first-admin bootstrap is needed. There are no seeded accounts or passwords.
Mail delivery is optional; use the Resend/SMTP settings in the example. SMTP on
the host needs `host.docker.internal`, not `localhost`.

Only ignored `.env.docker` supplies runtime secrets. It is excluded from both
builds, and no runtime secrets are build arguments. Do not publish expanded
`docker compose config` output, which can contain them. `config --quiet` validates
configuration without displaying values. Environment examples are public.

## Empty database: bootstrap once, then migrate

Alembic starts by altering existing tables. It cannot create a fresh CTRx database.
The reviewed `backend/docker/base-schema.sql` is a schema-only export of the
repository's `ctrx.backup`, without owners, ACLs, psql metacommands or data. It
includes changes through **20261127_rent_confirmation**. The database owner must
be able to create `btree_gist`, `citext` and `pgcrypto` (available in local
PostgreSQL and Neon). Use PostgreSQL 18 for this snapshot; older server versions
have not been validated.

```powershell
# ONLY for a new, empty database:
dc run --rm migrate python -m app.scripts.container_db bootstrap
dc run --rm migrate
dc run --rm migrate python -m app.scripts.seed_areas
dc run --rm migrate python -m app.scripts.container_db check
dc up -d --wait backend frontend
```

Bootstrap refuses any existing application relation in `public`, restores the
snapshot and records its exact revision in one transaction. It never drops or
cleans a schema. Upgrade refuses databases without a recorded base revision.
Bootstrap and upgrade use a session advisory lock to reject concurrent schema
commands; use a direct PostgreSQL connection for schema operations, especially
when a provider offers a transaction pooler. For Neon, use the direct hostname
in `.env.docker` while migrating, then the pooled hostname for normal API use.

For an **existing CTRx database**, back up database and media first, check its
recorded Alembic revision, then run only `dc run --rm migrate`. Do not bootstrap
or stamp `head` to hide a missing or mismatched base. A legacy database without
an Alembic revision needs a schema comparison and explicit baseline reconciliation.

Open [http://localhost:8080](http://localhost:8080). Configure `CTRX_HTTP_PORT`
and public URLs together if changing the port.

## Isolated local PostgreSQL and integration smoke test

Use a separate checkout/environment file for testing if `.env.docker` already
contains real credentials. This command set uses project `ctrx-docker-test`,
its own database and media volumes, and no published database port.

In `.env.docker`, set a random `POSTGRES_PASSWORD`, set `DATABASE_URL` to
`postgresql+psycopg://ctrx:URL_ENCODED_LOCAL_PASSWORD@db:5432/ctrx`, and
`TEST_DATABASE_URL` to the same local host with a separate test database name
(the smoke test uses `DATABASE_URL`; it does not create or use that test database).
Use `APP_ENV=development` for the plain HTTP smoke test so refresh cookies work.

```powershell
function dc { docker compose -p ctrx-docker-test --env-file .env.docker -f docker-compose.yml -f docker-compose.local.yml @args }
dc config --quiet
dc build
dc up -d --wait db
dc run --rm migrate python -m app.scripts.container_db bootstrap
dc run --rm migrate
dc run --rm migrate python -m app.scripts.seed_areas
dc up -d --wait backend frontend
dc run --rm -e CTRX_SMOKE_ALLOW_WRITE=1 migrate python -m app.scripts.container_smoke write --require-html-pdf
dc up -d --force-recreate --wait backend frontend
dc run --rm -e CTRX_SMOKE_ALLOW_WRITE=1 migrate python -m app.scripts.container_smoke verify
dc down
```

The smoke test refuses external database/API hosts. It checks built HTML and JS,
SPA routing, missing asset/API 404s, proxied database health/statistics,
registration/login/refresh, unauthorized and wrong-role routes, uploaded image
normalization and persistence, native WeasyPrint rendering and certificate PDF
storage. Verification logs in again and checks the photo and PDF after container
recreation. It writes random disposable account credentials to a test manifest
inside the test media volume. Never run it on a real database.

## Routine operations

Using the same `dc` function/project/files as startup:

| Action | Command |
| --- | --- |
| Start | `dc up -d --wait backend frontend` |
| Stop, retain volumes | `dc down` |
| Show state/logs | `dc ps` / `dc logs --tail=100 backend frontend` |
| Schema readiness | `dc run --rm migrate python -m app.scripts.container_db check` |
| Upgrade after code changes | `dc build`, `dc stop frontend backend`, `dc run --rm migrate`, `dc up -d --wait backend frontend` |
| Migration history | `dc run --rm migrate python -m alembic current` |

For a media backup without a temporary archive:
`dc cp backend:/app/storage ./media-backup` while writes are paused. Back up the
database separately using your PostgreSQL provider or `pg_dump`; database
metadata and media files belong to the same recovery set. Existing files are
not imported automatically: copy the old storage contents into the mounted
`/app/storage` before using the existing database. Default named volumes are
`<compose-project>_media` and, with the local overlay, `<compose-project>_pgdata`.
Keep the project name consistent. `down` retains both; `down -v` deliberately
deletes them and is suitable only when discarding the isolated test stack.

## Architecture and troubleshooting

Nginx serves Vite's production output on unprivileged port 8080 and proxies
`/api` and `/health` to `backend:8000` without removing the path prefix. Only the
frontend's loopback host port is published. `/healthz` checks static-server
liveness; `/health` checks the API/database. Backend health additionally requires
the recorded migration revision to match the application's head. The API runs
as UID/GID 10001; `/app/storage` is a persistent named volume. Both images include
repository Assets at the paths expected by their imports/renderers.

There are no migrations on startup, build or worker creation. Scale API workers
only after the one-shot migration finishes. The scheduler remains optional and
is not started by Compose.

| Symptom | Check/fix |
| --- | --- |
| Backend unhealthy / frontend waits | Inspect `dc logs backend`; check `/health` has `db: 1`, then run schema `check`. Missing schema requires the explicit empty-database bootstrap. |
| Connection refused | `localhost` inside a container is that container. Use `db`, an external hostname, or `host.docker.internal`. Check firewall and TLS settings. |
| Nginx 502 | Confirm backend health and service DNS. Nginx re-resolves Docker DNS when the backend is replaced. |
| Login works but refresh fails | Plain HTTP uses `APP_ENV=development`; production cookies require HTTPS. Keep frontend/API on the same origin. |
| Upload/PDF permission denied | Named volumes initialize with UID 10001. If substituting bind mounts, grant that UID write access. Never expose storage through a public static route. |
| PDF renderer fails | Build-time PDF smoke catches native library and pydyf mismatch. Rebuild from the pinned lock; do not independently upgrade pydyf for WeasyPrint 62. |
| Browser calls old backend | Docker deliberately copies no frontend `.env`; rebuild the image and clear browser cache. Do not use internal service names in Vite browser URLs. |
| Changing credentials has no effect | Recreate the affected container; `restart` alone does not reread env files. Local PostgreSQL init credentials apply only on an empty data volume. |

For public use, put TLS in front of Nginx, set `APP_ENV=production`, HTTPS public
frontend/verification URLs and JSON `CORS_ORIGINS`. The published port is loopback
by default; change the binding explicitly for another deployment topology.
The current proxy assumes a single edge. If adding another TLS proxy, configure
trusted forwarded-protocol handling there so redirects/links reflect HTTPS.

Frontend installs use `npm ci` and the tracked lockfile. Backend installs use
exact runtime pins in `requirements-docker.lock`, including the Linux-only loop
and scheduler dependencies; input constraints are in `docker/requirements.in`.
To update, resolve on Python 3.12 Linux with pip-tools, e.g.
`pip-compile --output-file requirements-docker.lock docker/requirements.in`,
then rebuild and run the isolated smoke test. Docker image version tags are
fixed, but tags and Debian package repositories can be republished; archive built
images or pin approved registry digests and an apt snapshot when byte-for-byte
reproduction is required. Registry resolution was unavailable in this session.

## Validation in this environment

- TypeScript no-emit check and Vite production build passed.
- 23 focused backend payment, certificate, sharing and reliability tests passed.
- Compose YAML parsing, Python compilation and direct runtime pin constraints
  passed. Local ReportLab certificate generation (with the repository image
  assets) and a PDF storage write/read round trip passed.
- Reviewed schema restored in a disposable PostgreSQL 18 cluster; Alembic's SQL
  from the snapshot revision through head executed successfully, ending at
  `20261201_tenancy_apartment`, with the apartment exclusion constraint present
  and zero users. PostgreSQL single-user mode was used because loopback TCP is
  blocked here.
- Docker is not installed and outbound package/registry access is unavailable.
  Image builds, Compose runtime/Nginx routing, API-to-database TCP, browser login,
  native Linux PDF rendering and Docker-volume persistence remain untested here.
  Use the isolated command sequence above to complete those checks.

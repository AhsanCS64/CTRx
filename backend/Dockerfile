# Build from repository root: docker build -f backend/Dockerfile .
FROM python:3.12.8-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# WeasyPrint native renderer, PostgreSQL library, and fonts including Bangla.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-dejavu-core fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements-docker.lock ./requirements-docker.lock
RUN pip install --no-cache-dir --no-deps --only-binary=:all: -r requirements-docker.lock && pip check
# Fail the build if native libraries or the renderer/PDF dependency pairing breaks.
RUN python -c "from weasyprint import HTML; assert HTML(string='<p>CTRx PDF readiness</p>').write_pdf().startswith(b'%PDF-')"
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/docker ./docker
COPY Assets /app/Assets
RUN groupadd --gid 10001 ctrx && useradd --uid 10001 --gid ctrx --no-create-home ctrx \
    && mkdir -p /app/storage && chown ctrx:ctrx /app/storage
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

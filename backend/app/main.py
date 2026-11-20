"""FastAPI application factory for the CTRx backend.

- Loads settings, configures CORS (credentials enabled for the origins list).
- Includes all router modules (they may be empty stubs for now).
- Registers a global exception handler that converts `ValueError` raised by
  `Settings` (missing secrets) into a 500 response.
- Sets up logging via ``app.core.logging.logger``.
- Performs a startup check that the required secret settings are present.
"""

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core import config, logging as log_mod
from app.api import routers  # package that imports all router modules
from app.db.session import SessionLocal
from sqlalchemy import text

logger = log_mod.logger


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    The function is imported by the ``uvicorn`` command (e.g. ``uvicorn
    app.main:create_app``). All routers are mounted under the ``/api`` prefix.
    """
    # Validate required secrets early – ``Settings`` raises ``ValueError`` if any
    # of the three secrets are empty (see ``core/config.py``).
    try:
        _ = config.settings  # trigger validation
    except ValueError as exc:
        logger.error("Missing required secret configuration", exc_info=exc)
        raise RuntimeError(str(exc)) from exc

    app = FastAPI(title="CENTRAL TENANCY RECORDS API", version="0.1.0")

    # ---------------------------------------------------------------------
    # CORS – credentials enabled because the refresh‑cookie is httpOnly.
    # ---------------------------------------------------------------------
    cors_origins = list(config.settings.CORS_ORIGINS or [])
    if config.settings.APP_ENV == "development":
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            if origin not in cors_origins:
                cors_origins.append(origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------------------
    # Include routers – each router file registers its own APIRouter with a
    # ``/api`` prefix inside the module.
    # ---------------------------------------------------------------------
    for router in routers.ALL_ROUTERS:
        app.include_router(router, prefix="/api")

    # ---------------------------------------------------------------------
    # Global exception handling – turn ``ValueError`` from services into a
    # clean JSON error response.
    # ---------------------------------------------------------------------
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):  # noqa: D401
        """Return a 400 response for ``ValueError`` raised in the code path."""
        logger.warning("ValueError: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):  # noqa: D401
        """Log the details and expose them only in development."""
        logger.exception("Unhandled exception: %s", exc)
        detail = (
            f"{type(exc).__name__}: {exc}"
            if config.settings.APP_ENV == "development"
            else "An unexpected server error occurred"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": detail},
        )

    @app.get("/health")
    def health():
        """Health check. Returns ``db: 1`` when a simple query against the
        configured database succeeds, otherwise ``db: 0``.
        """
        try:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1")).scalar_one()
                db_status = 1
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Health check DB query failed", exc_info=exc)
            db_status = 0
        return {"status": "ok", "db": db_status}

    return app

# The module‑level instance used by ``uvicorn``.
app = create_app()

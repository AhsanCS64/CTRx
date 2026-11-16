"""SQLAlchemy session factory.

Creates a **sync** ``SessionLocal`` bound to the ``DATABASE_URL`` defined in
``app.core.config.Settings``. The function ``get_db`` (used as a FastAPI
dependency) yields a session and ensures it is closed after the request.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# Engine – echo disabled (can be toggled via LOG_LEVEL if needed).
engine = create_engine(settings.DATABASE_URL, echo=False, future=True)

# ``SessionLocal`` is a factory for ``Session`` objects.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Session:
    """FastAPI dependency that provides a database session.

    Usage::

        def some_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

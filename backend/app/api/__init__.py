"""Package that aggregates all router modules for inclusion in ``app.main``."""

from app.api.routers import ALL_ROUTERS  # noqa: F401

__all__ = ["ALL_ROUTERS"]

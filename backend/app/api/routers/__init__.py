"""Aggregates every API router for inclusion in ``app.main``."""

from importlib import import_module
from typing import List

_router_modules = [
    "app.api.routers.auth",
    "app.api.routers.public",
    "app.api.routers.ric_applications",
    "app.api.routers.government",
    "app.api.routers.certificates",
    "app.api.routers.verification",
    "app.api.routers.payments",
    "app.api.routers.admin",
    "app.api.routers.disputes",
    "app.api.routers.properties",
    "app.api.routers.viewings",
    "app.api.routers.tenancies",
    "app.api.routers.rental_offers",
    "app.api.routers.rent",
    "app.api.routers.workspace",
    "app.api.routers.profile",
    "app.api.routers.rental_records",
    "app.api.routers.tenancy_care",
    "app.api.routers.support",
]

ALL_ROUTERS: List[object] = []
for _module_path in _router_modules:
    _mod = import_module(_module_path)
    if hasattr(_mod, "router"):
        ALL_ROUTERS.append(_mod.router)

__all__ = ["ALL_ROUTERS"]


"""Router registry for this service."""

from __future__ import annotations

from app.api.health import router as health_router
from app.api.releases import router as releases_router

ALL_ROUTERS = (health_router, releases_router)

__all__ = ["ALL_ROUTERS"]

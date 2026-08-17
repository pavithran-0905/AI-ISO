"""Router registry for this service."""

from __future__ import annotations

from app.api.health import router as health_router
from app.api.upgrade import router as upgrade_router

ALL_ROUTERS = (health_router, upgrade_router)

__all__ = ["ALL_ROUTERS"]

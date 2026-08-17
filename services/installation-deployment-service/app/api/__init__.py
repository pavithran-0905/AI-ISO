"""Router registry for this service."""

from __future__ import annotations

from app.api.deployment import router as deployment_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, deployment_router)

__all__ = ["ALL_ROUTERS"]

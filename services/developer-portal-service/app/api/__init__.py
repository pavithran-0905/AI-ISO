"""Every router this service exposes."""

from app.api.health import router as health_router
from app.api.portal import router as portal_router

ALL_ROUTERS = (health_router, portal_router)

__all__ = ["ALL_ROUTERS"]

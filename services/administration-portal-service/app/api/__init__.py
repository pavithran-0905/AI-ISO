"""Every router this service exposes."""

from app.api.admin import router as admin_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, admin_router)

__all__ = ["ALL_ROUTERS"]

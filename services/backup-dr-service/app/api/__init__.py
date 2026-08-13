"""Every router this service exposes."""

from app.api.backup import router as backup_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, backup_router)

__all__ = ["ALL_ROUTERS"]

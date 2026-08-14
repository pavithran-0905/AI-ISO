"""Every router this service exposes."""

from app.api.cloud import router as cloud_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, cloud_router)

__all__ = ["ALL_ROUTERS"]

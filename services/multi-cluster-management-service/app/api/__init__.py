"""Every router this service exposes."""

from app.api.clusters import router as clusters_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, clusters_router)

__all__ = ["ALL_ROUTERS"]

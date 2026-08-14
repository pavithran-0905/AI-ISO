"""Every router this service exposes."""

from app.api.edge import router as edge_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, edge_router)

__all__ = ["ALL_ROUTERS"]

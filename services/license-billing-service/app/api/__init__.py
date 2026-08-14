"""Every router this service exposes."""

from app.api.billing import router as billing_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, billing_router)

__all__ = ["ALL_ROUTERS"]

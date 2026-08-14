"""Every router this service exposes."""

from app.api.health import router as health_router
from app.api.mobile import router as mobile_router

ALL_ROUTERS = (health_router, mobile_router)

__all__ = ["ALL_ROUTERS"]

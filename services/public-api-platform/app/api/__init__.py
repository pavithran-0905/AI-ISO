"""Every router this service exposes."""

from app.api.health import router as health_router
from app.api.public_api import router as public_api_router

ALL_ROUTERS = (health_router, public_api_router)

__all__ = ["ALL_ROUTERS"]

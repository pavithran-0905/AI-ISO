"""Every router this service exposes."""

from app.api.health import router as health_router
from app.api.sdk_cli import router as sdk_cli_router

ALL_ROUTERS = (health_router, sdk_cli_router)

__all__ = ["ALL_ROUTERS"]

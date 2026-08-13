"""The HTTP API.

``ALL_ROUTERS`` is the single list the factory includes, in this order:
health first so probes are answered even if a business router later
fails to import, then the observability routes.
"""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.observability import router as observability_router

ALL_ROUTERS: tuple[APIRouter, ...] = (health_router, observability_router)

__all__ = ["ALL_ROUTERS", "health_router", "observability_router"]

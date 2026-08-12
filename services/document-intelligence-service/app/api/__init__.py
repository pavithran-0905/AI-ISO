"""The HTTP API.

``ALL_ROUTERS`` is the single list the factory includes, in this order:
health first so probes are answered even if a business router later fails
to import, then the document routes.
"""

from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.health import router as health_router

ALL_ROUTERS: tuple[APIRouter, ...] = (health_router, documents_router)

__all__ = ["ALL_ROUTERS", "documents_router", "health_router"]

"""Router registry for this service."""

from __future__ import annotations

from app.api.health import router as health_router
from app.api.qa import router as qa_router

ALL_ROUTERS = (health_router, qa_router)

__all__ = ["ALL_ROUTERS"]

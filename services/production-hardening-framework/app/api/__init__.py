"""Router registry for this service."""

from __future__ import annotations

from app.api.hardening import router as hardening_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, hardening_router)

__all__ = ["ALL_ROUTERS"]

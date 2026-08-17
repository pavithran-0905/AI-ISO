"""Router registry for this service."""

from __future__ import annotations

from app.api.benchmark import router as benchmark_router
from app.api.health import router as health_router

ALL_ROUTERS = (health_router, benchmark_router)

__all__ = ["ALL_ROUTERS"]

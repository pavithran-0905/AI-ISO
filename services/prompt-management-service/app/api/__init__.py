"""Every router this service exposes.

Order matters across the *whole app*, not just within one router:
FastAPI/Starlette matches routes in registration order. ``health_router``
owns only fixed root paths so it is safe anywhere; ``prompts_router``
manages its own internal static-before-catch-all ordering (see
:mod:`app.api.prompts`).
"""

from __future__ import annotations

from app.api.health import router as health_router
from app.api.prompts import router as prompts_router

ALL_ROUTERS = [health_router, prompts_router]

__all__ = ["ALL_ROUTERS", "health_router", "prompts_router"]

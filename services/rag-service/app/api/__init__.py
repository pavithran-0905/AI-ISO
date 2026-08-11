"""Every router this service exposes.

Order matters across the *whole app*, not just within one router:
FastAPI/Starlette matches routes in registration order. ``health_router``
owns only fixed root paths so it is safe anywhere; ``rag_router`` manages
its own internal static-before-catch-all ordering (see
:mod:`app.api.rag`).
"""

from __future__ import annotations

from app.api.health import router as health_router
from app.api.rag import router as rag_router

ALL_ROUTERS = [health_router, rag_router]

__all__ = ["ALL_ROUTERS", "health_router", "rag_router"]

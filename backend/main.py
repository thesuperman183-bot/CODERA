"""Main FastAPI application entrypoint for the refactored modular backend."""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.exceptions import register_exception_handlers
from backend.database import init_db
from backend.routers import (
    auth_router,
    dashboard_router,
    github_router,
    memories_router,
    pull_requests_router,
    reviews_router,
    team_rules_router,
    teams_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown routines."""
    try:
        await init_db()
        logging.info("[backend] Neon database tables verified/initialized.")
    except Exception as exc:
        logging.warning(f"[backend] Notice: Database auto-init skipped or failed: {exc}")
    yield


def create_app() -> FastAPI:
    """Application factory for Code Review Agent backend."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Modular AI-powered code review backend with long-term memory guidance.",
        lifespan=lifespan,
    )

    # Configure CORS for Next.js web dashboard
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Mount domain routers
    app.include_router(reviews_router)
    app.include_router(memories_router)
    app.include_router(team_rules_router)
    app.include_router(dashboard_router)
    app.include_router(auth_router)
    app.include_router(github_router)
    app.include_router(pull_requests_router)
    app.include_router(teams_router)

    @app.get("/health", tags=["Health"], summary="System health check")
    def health_check() -> dict[str, str]:
        return {"status": "ok", "version": settings.VERSION}

    @app.get("/", tags=["Health"], summary="API Root")
    def root() -> dict[str, str]:
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)


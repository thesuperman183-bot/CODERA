"""API routers package."""
from backend.routers.reviews import router as reviews_router
from backend.routers.memories import router as memories_router
from backend.routers.team_rules import router as team_rules_router
from backend.routers.dashboard import router as dashboard_router
from backend.routers.auth import router as auth_router
from backend.routers.github import router as github_router
from backend.routers.pull_requests import router as pull_requests_router
from backend.routers.teams import router as teams_router

__all__ = [
    "reviews_router",
    "memories_router",
    "team_rules_router",
    "dashboard_router",
    "auth_router",
    "github_router",
    "pull_requests_router",
    "teams_router",
]


"""Root entrypoint proxying to the modular backend package.

Maintains backward compatibility with commands like `uvicorn main:app`.
"""
from __future__ import annotations

from backend.main import app, create_app
from backend.schemas import (
    RetainRequest,
    RetainResponse,
    ReviewRequest,
    ReviewResponse,
)
from backend.services.hindsight_service import HindsightError, recall_memory, retain_memory

__all__ = [
    "app",
    "create_app",
    "RetainRequest",
    "RetainResponse",
    "ReviewRequest",
    "ReviewResponse",
    "HindsightError",
    "recall_memory",
    "retain_memory",
]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

"""Root proxy for Hindsight Cloud service maintaining backward compatibility."""
from __future__ import annotations

from backend.services.hindsight_service import (
    DEFAULT_HINDSIGHT_URL,
    HindsightError,
    HindsightMemoryService,
    hindsight_service,
    recall_memory,
    retain_memory,
)

DEFAULT_BASE_URL = DEFAULT_HINDSIGHT_URL

__all__ = [
    "DEFAULT_BASE_URL",
    "HindsightError",
    "HindsightMemoryService",
    "hindsight_service",
    "recall_memory",
    "retain_memory",
]

"""Hindsight Cloud REST adapter."""
import os
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_BASE_URL = "https://cloud.vectorize.io/api/v1"


class HindsightError(RuntimeError):
    """Raised when Hindsight configuration or a provider response is invalid."""


def _config() -> tuple[str, str, float]:
    key = os.getenv("HINDSIGHT_API_KEY", "").strip()
    if not key:
        raise HindsightError("HINDSIGHT_API_KEY is not configured")
    base = os.getenv("HINDSIGHT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    try:
        timeout = float(os.getenv("HINDSIGHT_TIMEOUT_SECONDS", "15"))
    except ValueError as exc:
        raise HindsightError("HINDSIGHT_TIMEOUT_SECONDS must be numeric") from exc
    if timeout <= 0:
        raise HindsightError("HINDSIGHT_TIMEOUT_SECONDS must be positive")
    return key, base, timeout


def _bank_url(base: str, bank_id: str) -> str:
    if not bank_id.strip():
        raise HindsightError("HINDSIGHT_BANK_ID is not configured")
    return f"{base}/default/banks/{quote(bank_id, safe='')}"


def _post(url: str, payload: dict[str, Any], key: str, timeout: float) -> dict[str, Any]:
    try:
        response = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Do not expose provider response bodies in errors.
        raise HindsightError("Hindsight request failed") from exc
    if not isinstance(result, dict):
        raise HindsightError("Hindsight returned an invalid response")
    return result


def retain_memory(bank_id: str, content: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Store content and optional document metadata in the configured bank."""
    if not content.strip():
        raise HindsightError("content must not be empty")
    key, base, timeout = _config()
    payload: dict[str, Any] = {
        "items": [{"content": content}],
        "document_metadata": metadata,
    }
    tags = metadata.get("tags")
    if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
        payload["tags"] = tags
    result = _post(f"{_bank_url(base, bank_id)}/memories", payload, key, timeout)
    if result.get("success") is False:
        raise HindsightError("Hindsight did not retain the rule")
    return result


def recall_memory(bank_id: str, query: str, top_k: int = 5) -> list[str]:
    """Return recalled memory text, with provider failures surfaced as errors."""
    if not query.strip():
        raise HindsightError("query must not be empty")
    if top_k < 1:
        raise HindsightError("top_k must be positive")
    key, base, timeout = _config()
    result = _post(
        f"{_bank_url(base, bank_id)}/memories/recall",
        {"query": query, "limit": top_k},
        key,
        timeout,
    )
    rows = result.get("results")
    if not isinstance(rows, list):
        raise HindsightError("Hindsight returned an invalid recall response")
    memories = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            raise HindsightError("Hindsight returned an invalid memory")
        memories.append(row["text"])
    return memories

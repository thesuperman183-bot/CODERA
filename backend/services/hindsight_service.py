"""Service for Hindsight Cloud long-term memory retention and recall."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote
import httpx

from backend.core.config import settings
from backend.core.exceptions import ConfigurationError, HindsightServiceError

# Backward compatibility alias
HindsightError = HindsightServiceError
DEFAULT_HINDSIGHT_URL = settings.DEFAULT_HINDSIGHT_URL


class HindsightMemoryService:
    """Adapter for Hindsight Cloud memory retention and recall REST APIs."""

    def __init__(self, http_client: Optional[httpx.Client] = None):
        self._client = http_client

    def _get_client(self) -> httpx.Client:
        return self._client or httpx.Client()

    def _bank_url(self, bank_id: Optional[str] = None) -> str:
        bid = (bank_id or settings.hindsight_bank_id).strip()
        if not bid:
            raise ConfigurationError("HINDSIGHT_BANK_ID is not configured")
        base = settings.hindsight_base_url
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}/default/banks/{quote(bid, safe='')}"

    def _post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        key = settings.hindsight_api_key
        if not key:
            raise ConfigurationError("HINDSIGHT_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            client = self._get_client()
            response = client.post(
                url,
                json=payload,
                headers=headers,
                timeout=settings.hindsight_timeout_seconds,
            )
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as exc:
            raise HindsightServiceError(
                f"Hindsight request failed with HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise HindsightServiceError("Hindsight request failed") from exc

        if not isinstance(result, dict):
            raise HindsightServiceError("Hindsight returned an invalid response")
        return result

    def retain(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Store content rule and metadata in the configured memory bank."""
        if not content.strip():
            raise HindsightServiceError("content must not be empty")

        meta = metadata or {}
        payload: Dict[str, Any] = {
            "items": [{"content": content}],
            "document_metadata": meta,
        }
        tags = meta.get("tags")
        if isinstance(tags, list) and all(isinstance(t, str) for t in tags):
            payload["tags"] = tags

        url = f"{self._bank_url(bank_id)}/memories"
        result = self._post(url, payload)

        if result.get("success") is False:
            raise HindsightServiceError("Hindsight did not retain the rule")
        return result

    def recall(
        self,
        query: str,
        top_k: int = 5,
        bank_id: Optional[str] = None,
    ) -> List[str]:
        """Query memory bank for relevant rules matching query/diff."""
        if not query.strip():
            raise HindsightServiceError("query must not be empty")
        if top_k < 1:
            raise HindsightServiceError("top_k must be positive")

        url = f"{self._bank_url(bank_id)}/memories/recall"
        payload = {"query": query, "limit": top_k}
        result = self._post(url, payload)

        rows = result.get("results")
        if not isinstance(rows, list):
            raise HindsightServiceError("Hindsight returned an invalid recall response")

        memories: List[str] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str):
                raise HindsightServiceError("Hindsight returned an invalid memory")
            memories.append(row["text"])
        return memories


hindsight_service = HindsightMemoryService()


# Backward-compatible functional interface
def retain_memory(bank_id: str, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Store content and metadata in Hindsight (legacy signature)."""
    return hindsight_service.retain(content=content, metadata=metadata, bank_id=bank_id)


def recall_memory(bank_id: str, query: str, top_k: int = 5) -> List[str]:
    """Recall relevant memory strings from Hindsight (legacy signature)."""
    return hindsight_service.recall(query=query, top_k=top_k, bank_id=bank_id)

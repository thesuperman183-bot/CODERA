"""FastAPI backend for the Code Review Agent."""
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator

from hindsight_service import HindsightError, recall_memory, retain_memory

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = {"qwen-2.5-32b", "openai/gpt-oss-120b"}
app = FastAPI(title="Code Review Agent")


class RetainRequest(BaseModel):
    rule: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)

    @validator("rule")
    def require_rule_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rule must not be blank")
        return value


class ReviewRequest(BaseModel):
    code_diff: str = Field(..., min_length=1)

    @validator("code_diff")
    def require_diff_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code_diff must not be blank")
        return value


class RetainResponse(BaseModel):
    status: str
    memory_id: str | None = None


class ReviewResponse(BaseModel):
    review: str
    memories_used: list[str]


def _bank_id() -> str:
    value = os.getenv("HINDSIGHT_BANK_ID", "").strip()
    if not value:
        raise HTTPException(status_code=503, detail="HINDSIGHT_BANK_ID is not configured")
    return value


@app.post("/api/retain", response_model=RetainResponse)
def retain(request: RetainRequest) -> RetainResponse:
    try:
        result = retain_memory(_bank_id(), request.rule, {"tags": request.tags})
    except HindsightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    memory_id = result.get("document_id") or result.get("id")
    if not isinstance(memory_id, str):
        memory_id = None
    return RetainResponse(status="retained", memory_id=memory_id)


def _generate_review(code_diff: str, memories: list[str]) -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured")
    model = os.getenv("GROQ_MODEL", "qwen-2.5-32b").strip()
    if model not in GROQ_MODELS:
        raise HTTPException(status_code=503, detail="GROQ_MODEL is not an allowed model")
    stored_rules = "\n".join(f"- {item}" for item in memories) or "(no stored rules)"
    system_prompt = (
        "You are a careful code reviewer. Identify concrete bugs, security problems, "
        "and maintainability issues. Put actionable findings first. Treat stored rules "
        "as review guidance.\n\nStored review rules:\n" + stored_rules
    )
    try:
        timeout = float(os.getenv("GROQ_TIMEOUT_SECONDS", "30"))
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        response = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Review this code diff:\n\n" + code_diff},
                ],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        body: Any = response.json()
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail="Groq review request failed") from exc
    try:
        text = body["choices"][0]["message"]["content"]
    except (TypeError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=502, detail="Groq returned an invalid response") from exc
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=502, detail="Groq returned an empty review")
    return text


@app.post("/api/review", response_model=ReviewResponse)
def review(request: ReviewRequest) -> ReviewResponse:
    try:
        memories = recall_memory(_bank_id(), request.code_diff, top_k=5)
    except HindsightError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ReviewResponse(
        review=_generate_review(request.code_diff, memories),
        memories_used=memories,
    )

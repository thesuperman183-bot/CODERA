"""Centralized configuration management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Set

from dotenv import load_dotenv

# Automatically load .env from project root if it exists
_root_dir = Path(__file__).resolve().parents[2]
_env_path = _root_dir / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()


class Settings:
    """Application settings resolved from environment variables."""

    # Project metadata
    PROJECT_NAME: str = "CODERA"
    VERSION: str = "0.2.0"
    API_V1_STR: str = "/api"

    # Groq API configuration
    GROQ_URL: str = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
    ALLOWED_GROQ_MODELS: Set[str] = {
        "qwen-2.5-32b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "llama-3.3-70b-versatile",
        "qwen-2.5-coder-32b",
        "deepseek-r1-distill-llama-70b",
    }

    # Hindsight Cloud configuration
    DEFAULT_HINDSIGHT_URL: str = "https://cloud.vectorize.io/api/v1"

    @property
    def groq_api_key(self) -> str:
        """Resolve Groq API key with fallback to legacy env var."""
        key = os.getenv("GROQ_API_KEY") or os.getenv("groq_api", "")
        return key.strip()

    @property
    def groq_model(self) -> str:
        """Resolve Groq model name with automatic fallback for decommissioned models."""
        raw = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
        if raw in ("qwen-2.5-32b", "llama-3.1-70b-versatile"):
            return "openai/gpt-oss-120b"
        return raw or "openai/gpt-oss-120b"

    @property
    def groq_timeout_seconds(self) -> float:
        """Timeout for Groq API calls in seconds."""
        try:
            val = float(os.getenv("GROQ_TIMEOUT_SECONDS", "30.0"))
            return val if val > 0 else 30.0
        except ValueError:
            return 30.0

    @property
    def hindsight_api_key(self) -> str:
        """Resolve Hindsight API key with fallback to legacy env var."""
        key = os.getenv("HINDSIGHT_API_KEY") or os.getenv("Hindsight_api", "")
        return key.strip()

    @property
    def hindsight_base_url(self) -> str:
        """Resolve Hindsight base URL with fallback to legacy env var."""
        base = os.getenv("HINDSIGHT_BASE_URL") or os.getenv("Hindsight_end_point") or self.DEFAULT_HINDSIGHT_URL
        return base.rstrip("/")

    @property
    def hindsight_bank_id(self) -> str:
        """Resolve Hindsight bank ID."""
        return os.getenv("HINDSIGHT_BANK_ID", "default").strip()

    @property
    def hindsight_timeout_seconds(self) -> float:
        """Timeout for Hindsight API calls in seconds."""
        try:
            val = float(os.getenv("HINDSIGHT_TIMEOUT_SECONDS", "15.0"))
            return val if val > 0 else 15.0
        except ValueError:
            return 15.0

    @property
    def database_url(self) -> str:
        """Neon PostgreSQL connection URL."""
        return os.getenv("DATABASE_URL", "").strip()

    @property
    def async_database_url(self) -> str:
        """Database URL formatted for asyncpg driver."""
        raw = self.database_url
        if not raw:
            return ""
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        u = urlparse(raw)
        q = dict(parse_qsl(u.query))
        # Remove parameters not directly accepted by asyncpg
        q.pop("channel_binding", None)
        q.pop("sslmode", None)
        return urlunparse(
            ("postgresql+asyncpg", u.netloc, u.path, u.params, urlencode(q), u.fragment)
        )

    @property
    def neon_auth_base_url(self) -> str:
        """Neon Managed Better Auth base URL."""
        return os.getenv("NEON_AUTH_BASE_URL", "").strip()

    @property
    def neon_auth_jwks_url(self) -> str:
        """Neon Auth JWKS URL for JWT signature verification."""
        return os.getenv("NEON_AUTH_JWKS_URL", "").strip()

    @property
    def cors_origins(self) -> list[str]:
        """Allowed origins for CORS supporting JSON array, comma-separated strings, or wildcards."""
        origins = os.getenv("CORS_ORIGINS", '["http://localhost:3000","http://127.0.0.1:3000"]')
        try:
            import json
            parsed = json.loads(origins)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        if "," in origins:
            return [o.strip() for o in origins.split(",") if o.strip()]
        if origins.strip() and origins.strip() != "*":
            return [origins.strip()]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    # -------------------------------------------------------------------------
    # GitHub App & OAuth Integration Settings
    # -------------------------------------------------------------------------
    @property
    def github_client_id(self) -> str:
        """GitHub App / OAuth Client ID."""
        return os.getenv("GITHUB_CLIENT_ID", "").strip()

    @property
    def github_client_secret(self) -> str:
        """GitHub App / OAuth Client Secret."""
        return os.getenv("GITHUB_CLIENT_SECRET", "").strip()

    @property
    def github_app_id(self) -> str:
        """GitHub App ID."""
        return os.getenv("GITHUB_APP_ID", "").strip()

    @property
    def github_private_key(self) -> str:
        """GitHub App Private Key (PEM format or path to file)."""
        return os.getenv("GITHUB_PRIVATE_KEY", "").strip()

    @property
    def github_webhook_secret(self) -> str:
        """GitHub Webhook secret for payload signature validation."""
        return os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()

    @property
    def github_api_base_url(self) -> str:
        """GitHub REST API base URL."""
        return os.getenv("GITHUB_API_BASE_URL", "https://api.github.com").rstrip("/")



settings = Settings()


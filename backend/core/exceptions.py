"""Centralized error definitions and HTTP exception handlers."""
from __future__ import annotations

from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class ConfigurationError(AppException):
    """Raised when an essential service configuration or API key is missing."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=503)


class HindsightServiceError(AppException):
    """Raised when Hindsight Cloud request or response fails."""

    def __init__(self, message: str = "Hindsight request failed", details: Any = None):
        super().__init__(message=message, status_code=502, details=details)


class GroqServiceError(AppException):
    """Raised when Groq API request or completion generation fails."""

    def __init__(self, message: str = "Groq review request failed", details: Any = None):
        super().__init__(message=message, status_code=502, details=details)


class InvalidInputError(AppException):
    """Raised when client input is invalid."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=400)


class ResourceNotFoundError(AppException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=404)


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        content = {"detail": exc.message}
        if exc.details:
            content["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=content)


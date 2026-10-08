"""Turns every exception into a friendly {"error": {code, message}} response.

Details are logged on the server; the browser never sees stack traces or secrets.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.providers.base import (
    ApiKeyMissingError,
    AuthError,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimitError,
)
from app.services.response_formatter import InvalidAIResponse

logger = logging.getLogger(__name__)

# exception type -> (HTTP status, error code, user-facing message)
_ERROR_TABLE: list[tuple[type[Exception], int, str, str]] = [
    (ApiKeyMissingError, 503, "API_KEY_MISSING",
     "Gemini API key is not set. Add GEMINI_API_KEY to your .env file and restart the server."),
    (AuthError, 503, "API_KEY_INVALID",
     "The Gemini API key was rejected. Please check GEMINI_API_KEY in your .env file."),
    (RateLimitError, 429, "RATE_LIMITED",
     "Professor is busy right now. Please try again in a moment."),
    (ProviderTimeout, 504, "TIMEOUT",
     "Professor took too long to answer. Please try again."),
    (ProviderUnavailable, 502, "PROVIDER_UNAVAILABLE",
     "Professor is temporarily unavailable. Please try again."),
    (InvalidAIResponse, 502, "INVALID_AI_RESPONSE",
     "Professor's answer came out garbled. Please try again."),
]


def error_body(code: str, message: str, details: list | None = None) -> dict:
    error: dict = {"code": code, "message": message}
    if details:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        first = details[0]["message"] if details else "Invalid request"
        first = first.removeprefix("Value error, ")
        return JSONResponse(status_code=422, content=error_body("VALIDATION_ERROR", first, details))

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(status_code=exc.status_code, content=error_body(code, str(exc.detail)))

    @app.exception_handler(ProviderError)
    @app.exception_handler(InvalidAIResponse)
    async def known_error_handler(_: Request, exc: Exception) -> JSONResponse:
        for exc_type, status, code, message in _ERROR_TABLE:
            if isinstance(exc, exc_type):
                logger.warning("%s: %s", code, exc)
                return JSONResponse(status_code=status, content=error_body(code, message))
        return await unexpected_handler(_, exc)

    @app.exception_handler(Exception)
    async def unexpected_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected server error")
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "Something went wrong on our side. Please try again."),
        )

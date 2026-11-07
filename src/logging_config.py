"""Structured logging configuration with correlation IDs."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

# Context variable for correlation ID
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str:
    """Get current correlation ID or generate a new one."""
    cid = correlation_id_var.get()
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        correlation_id_var.set(cid)
    return cid


def set_correlation_id(cid: str | None = None) -> str:
    """Set correlation ID for current context."""
    if cid is None:
        cid = str(uuid.uuid4())[:8]
    correlation_id_var.set(cid)
    return cid


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Configure structured logging with correlation IDs."""
    # Clear existing handlers
    logging.getLogger().handlers.clear()

    # Configure stdlib logging
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(CorrelationIdFilter())
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Configure structlog
    if log_format.lower() == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_with_context(
    logger: structlog.BoundLogger,
    level: str,
    message: str,
    **kwargs: Any,
) -> None:
    """Log with correlation ID and additional context."""
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, correlation_id=get_correlation_id(), **kwargs)


# FastAPI middleware for correlation IDs
class CorrelationIdMiddleware:
    """ASGI middleware to add correlation IDs to requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract or generate correlation ID
        correlation_id = None
        headers = dict(scope.get("headers", []))
        if b"x-correlation-id" in headers:
            correlation_id = headers[b"x-correlation-id"].decode()
        elif b"x-request-id" in headers:
            correlation_id = headers[b"x-request-id"].decode()

        set_correlation_id(correlation_id)

        async def send_wrapper(message):
            # Add correlation ID to response headers
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-correlation-id", get_correlation_id().encode())
                )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            correlation_id_var.set(None)


__all__ = [
    "configure_logging",
    "get_logger",
    "get_correlation_id",
    "set_correlation_id",
    "log_with_context",
    "CorrelationIdMiddleware",
]
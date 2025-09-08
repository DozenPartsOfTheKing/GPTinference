"""Logging middleware built on Loguru."""

from typing import Any
import time
import uuid

from .loguru_config import setup_loguru, get_logger


def setup_logging() -> None:
    """Initialize Loguru-based logging (kept for backward compatibility)."""
    setup_loguru()


class LoggingMiddleware:
    """HTTP logging middleware using Loguru with request-id context."""

    def __init__(self, app: Any):
        self.app = app
        self.base_logger = get_logger("middleware.logging")

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        query_string = scope.get("query_string", b"").decode()
        client = scope.get("client", ("unknown", 0))
        request_id = str(uuid.uuid4())

        # Bind context for this request
        logger = self.base_logger.bind(
            request_id=request_id,
            method=method,
            path=path,
            client_ip=client[0],
            client_port=client[1],
        )

        # Attach request_id to scope via state when available (FastAPI/Starlette)
        try:
            if "app" in scope:
                # Starlette/FastAPI populate state via Request object; we set in scope for later retrieval
                scope.setdefault("state", {})
                scope["state"]["request_id"] = request_id
        except Exception:
            pass

        start_time = time.time()
        logger.info(
            f"➡️ Request started{f' ?{query_string}' if query_string else ''}"
        )

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                status_code = message.get("status", 0)
                processing_time = time.time() - start_time
                logger.bind(status_code=status_code, duration_ms=int(processing_time * 1000)).info(
                    "✅ Request completed"
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)

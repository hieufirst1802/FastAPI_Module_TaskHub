import logging
from time import perf_counter

from fastapi import status
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Log HTTP requests and add timing to the response headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        async def send_with_timing(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Process-Time"] = (
                    f"{perf_counter() - started_at:.6f}"
                )
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        finally:
            logger.info(
                "%s %s %s %.6fs",
                scope["method"],
                scope["path"],
                status_code,
                perf_counter() - started_at,
            )

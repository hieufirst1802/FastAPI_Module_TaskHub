import logging
from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log request metadata and expose processing time in the response."""

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        started_at = perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            elapsed = perf_counter() - started_at
            response.headers["X-Process-Time"] = f"{elapsed:.6f}"
            return response
        except Exception:
            logger.exception(
                "Request failed: %s %s",
                request.method,
                request.url.path,
            )
            raise
        finally:
            elapsed = perf_counter() - started_at
            logger.info(
                "%s %s %s %.6fs",
                request.method,
                request.url.path,
                status_code,
                elapsed,
            )

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exception_handlers import unhandled_exception_handler


class UnhandledErrorMiddleware:
    """Turn unhandled HTTP errors into responses before headers have been sent."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def track_start(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, track_start)
        except Exception as exc:
            if response_started:
                raise
            response = await unhandled_exception_handler(Request(scope, receive), exc)
            await response(scope, receive, send)

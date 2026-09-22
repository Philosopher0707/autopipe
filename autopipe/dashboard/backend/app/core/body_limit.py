"""Request-body size enforcement.

Invariant I18: a security control that is claimed must actually execute.

The application used to declare ``max_request_body=10 * 1024 * 1024`` in the
``FastAPI(...)`` constructor. FastAPI has no such parameter, so the value was
silently stored in ``FastAPI.extra`` and never applied — the documented 10 MB
limit did not exist, while the accompanying comment claimed it prevented memory
exhaustion. This middleware is the actual control.

Two paths, because there are two ways a body arrives:

* **Declared length** (``Content-Length``): rejected before a single body byte is
  read. This is the common case for JSON APIs (browsers, axios and httpx all set
  it) and the cheap one.
* **Streamed body** (chunked, no ``Content-Length``): the ``receive`` channel is
  wrapped so bytes are counted as they arrive and the request is abandoned once
  the limit is passed.

The middleware is deliberately pure ASGI rather than
``BaseHTTPMiddleware``: the latter buffers the body, which would defeat the
purpose of the limit.
"""

import json
import logging

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

#: HTTP 413 Payload Too Large
STATUS_PAYLOAD_TOO_LARGE = 413


class _BodyTooLargeError(Exception):
    """Internal signal: the streamed body crossed the configured limit."""


class RequestSizeLimitMiddleware:
    """Reject requests whose body exceeds ``max_bytes``.

    Args:
        app: The wrapped ASGI application.
        max_bytes: Maximum permitted body size in bytes.
        exempt_paths: Path prefixes that bypass the check (e.g. endpoints that
            implement their own, larger, upload limit).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_bytes: int,
        exempt_paths: tuple[str, ...] = (),
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce the limit for HTTP requests, pass everything else through."""
        if scope["type"] != "http" or self._is_exempt(scope):
            await self.app(scope, receive, send)
            return

        declared = self._declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await self._reject(send, declared)
            return

        received = 0
        response_started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLargeError
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLargeError:
            if response_started:
                # A response is already on the wire; the only correct action is
                # to stop. Rethink the limit instead of corrupting the stream.
                logger.error(
                    "Body exceeded %d bytes after the response started; closing",
                    self.max_bytes,
                )
                raise
            await self._reject(send, received)

    def _is_exempt(self, scope: Scope) -> bool:
        if not self.exempt_paths:
            return False
        path = str(scope.get("path", ""))
        return any(path.startswith(prefix) for prefix in self.exempt_paths)

    @staticmethod
    def _declared_length(scope: Scope) -> int | None:
        raw = Headers(scope=scope).get("content-length")
        if raw is None or not raw.isdigit():
            return None
        return int(raw)

    async def _reject(self, send: Send, observed: int) -> None:
        """Send a 413 and stop reading."""
        logger.warning("Rejected request body of %d bytes (limit %d)", observed, self.max_bytes)
        payload = json.dumps(
            {
                "detail": (
                    f"Request body too large: {observed} bytes exceeds the "
                    f"{self.max_bytes} byte limit"
                )
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": STATUS_PAYLOAD_TOO_LARGE,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})


__all__ = ["STATUS_PAYLOAD_TOO_LARGE", "RequestSizeLimitMiddleware"]

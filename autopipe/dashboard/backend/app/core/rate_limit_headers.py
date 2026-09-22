"""Rate-limit response headers middleware.

``CORSMiddleware.expose_headers`` can only expose headers that are actually
present on a response.  The limiter previously raised mid-handler, so nothing
emitted ``X-RateLimit-*``; CORS claimed to expose headers that were never
there.  This middleware stamps them onto every response from a value the
``check_default_rate_limit`` dependency recorded on ``request.state``.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimitHeadersMiddleware(BaseHTTPMiddleware):
    """Attach ``X-RateLimit-*`` headers when the limiter recorded them."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        limit = getattr(request.state, "rate_limit_limit", None)
        remaining = getattr(request.state, "rate_limit_remaining", None)

        if limit is not None:
            response.headers["X-RateLimit-Limit"] = str(limit)
        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))

        return response

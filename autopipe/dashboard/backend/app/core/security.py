"""Security utilities - rate limiting and protection.

Simple in-memory rate limiting (no Redis required).
For production with Redis, migrate to fastapi-limiter properly.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass

from app.core.config import settings
from fastapi import HTTPException, Request, WebSocket, status
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class RateLimitEntry:
    """Track rate limit for a client."""

    count: int
    reset_time: float


class SimpleRateLimiter:
    """Simple in-memory rate limiter (not suitable for multi-instance deployments)."""

    def __init__(self):
        self._storage: dict[str, RateLimitEntry] = defaultdict(lambda: RateLimitEntry(0, 0))
        self._cleanup_interval = 3600  # 1 hour
        self._last_cleanup = time.time()

    def _get_client_key(self, request: Request | WebSocket) -> str:
        """Extract the client identifier used to key rate limits.

        ``X-Forwarded-For`` / ``X-Real-IP`` are honoured **only** when
        ``TRUST_PROXY_HEADERS`` is enabled, i.e. when the deployment actually
        sits behind a proxy that overwrites them. Trusting them unconditionally
        let any client present a fresh forged address per request and never hit
        a limit; the peer address is the only value the client cannot choose.
        """
        if settings.TRUST_PROXY_HEADERS:
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()

            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip

        return request.client.host if request.client else "unknown"

    def _cleanup_expired(self) -> None:
        """Remove expired entries periodically."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = [key for key, entry in self._storage.items() if entry.reset_time < now]
        for key in expired_keys:
            del self._storage[key]

        self._last_cleanup = now
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit entries")

    def reset(self) -> None:
        """Clear all rate limit entries (useful for testing)."""
        self._storage.clear()
        self._last_cleanup = time.time()
        logger.debug("Rate limit storage reset")

    def check_rate_limit(
        self,
        request: Request | WebSocket,
        times: int,
        seconds: int,
        identifier: str = "",
    ) -> tuple[int, int]:
        """
        Check if request exceeds rate limit.

        Args:
            request: FastAPI request
            times: Number of allowed requests
            seconds: Time window in seconds
            identifier: Additional identifier for the endpoint

        Returns:
            ``(remaining, limit)`` for this window, recorded on
            ``request.state`` so the header middleware can stamp them.

        Raises:
            HTTPException: If rate limit exceeded (429 with ``Retry-After`` and
                ``X-RateLimit-*`` headers).
        """
        # Skip rate limiting if request is None (e.g., in test mode with httpx.AsyncClient)
        if request is None:
            return (times, times)

        self._cleanup_expired()

        client_key = self._get_client_key(request)
        key = f"{client_key}:{identifier}"

        now = time.time()
        entry = self._storage[key]

        # Reset if window has passed
        if now > entry.reset_time:
            entry.count = 0
            entry.reset_time = now + seconds

        entry.count += 1

        remaining = max(times - entry.count, 0)

        # Record on request.state so RateLimitHeadersMiddleware can stamp them
        # onto the response even when the handler completes normally.
        request.state.rate_limit_limit = times
        request.state.rate_limit_remaining = remaining

        if entry.count > times:
            logger.warning(f"Rate limit exceeded for {client_key} on {identifier}")
            retry_after = int(entry.reset_time - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(times),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return (remaining, times)


# Global rate limiter instance
_rate_limiter = SimpleRateLimiter()


def check_login_rate_limit(request: Request) -> None:
    """Check rate limit for login attempts."""
    _rate_limiter.check_rate_limit(
        request,
        settings.RATE_LIMIT_LOGIN_REQUESTS,
        settings.RATE_LIMIT_LOGIN_WINDOW,
        identifier="login",
    )


def check_register_rate_limit(request: Request) -> None:
    """Check rate limit for registration attempts."""
    _rate_limiter.check_rate_limit(
        request,
        settings.RATE_LIMIT_REGISTER_REQUESTS,
        settings.RATE_LIMIT_REGISTER_WINDOW,
        identifier="register",
    )


def check_default_rate_limit(request: Request) -> tuple[int, int]:
    """Default rate limit for API endpoints (router-level dependency)."""
    return _rate_limiter.check_rate_limit(
        request,
        settings.RATE_LIMIT_DEFAULT_REQUESTS,
        settings.RATE_LIMIT_DEFAULT_WINDOW,
        identifier="api",
    )


async def check_websocket_rate_limit(websocket: WebSocket) -> None:
    """Default budget for WebSocket handshakes — same peer bucket as HTTP.

    FastAPI (0.109) does not inject ``Request`` into dependencies on
    WebSocket routes, but ``WebSocket`` exposes the same ``headers`` /
    ``client`` / ``state`` surface the limiter keys on, so the identical
    rule applies: handshake hammering spends the per-peer default budget.

    A WS handshake has no 429 status. Raising ``HTTPException`` on a
    websocket scope hangs the handshake (observed with TestClient), so the
    overload refuses the upgrade — close 1013 (try again later) before
    accept, then ``WebSocketDisconnect`` to short-circuit the endpoint.
    """
    try:
        _rate_limiter.check_rate_limit(
            websocket,
            settings.RATE_LIMIT_DEFAULT_REQUESTS,
            settings.RATE_LIMIT_DEFAULT_WINDOW,
            identifier="api",
        )
    except HTTPException as exc:
        retry_after = (exc.headers or {}).get("Retry-After", "?")
        await websocket.close(code=1013, reason=f"rate limited; retry after {retry_after}s")
        raise WebSocketDisconnect(code=1013, reason="rate limited") from None


async def setup_rate_limiter() -> None:
    """Initialize rate limiter (no-op for simple version)."""
    logger.info("Simple in-memory rate limiter initialized")


async def close_rate_limiter() -> None:
    """Cleanup rate limiter (no-op for simple version)."""

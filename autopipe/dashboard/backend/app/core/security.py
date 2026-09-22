"""Security utilities - rate limiting and protection.

Simple in-memory rate limiting (no Redis required).
For production with Redis, migrate to fastapi-limiter properly.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass

from app.core.config import settings
from fastapi import HTTPException, Request, status

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

    def _get_client_key(self, request: Request) -> str:
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
        request: Request,
        times: int,
        seconds: int,
        identifier: str = "",
    ) -> None:
        """
        Check if request exceeds rate limit.

        Args:
            request: FastAPI request
            times: Number of allowed requests
            seconds: Time window in seconds
            identifier: Additional identifier for the endpoint

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Skip rate limiting if request is None (e.g., in test mode with httpx.AsyncClient)
        if request is None:
            return

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

        if entry.count > times:
            logger.warning(f"Rate limit exceeded for {client_key} on {identifier}")
            retry_after = int(entry.reset_time - now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(retry_after)},
            )


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


def check_default_rate_limit(request: Request) -> None:
    """Check default rate limit for API endpoints."""
    _rate_limiter.check_rate_limit(
        request,
        settings.RATE_LIMIT_DEFAULT_REQUESTS,
        settings.RATE_LIMIT_DEFAULT_WINDOW,
        identifier="api",
    )


async def setup_rate_limiter() -> None:
    """Initialize rate limiter (no-op for simple version)."""
    logger.info("Simple in-memory rate limiter initialized")


async def close_rate_limiter() -> None:
    """Cleanup rate limiter (no-op for simple version)."""

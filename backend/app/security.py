"""Security, sanitization, rate limiting, and HTTP defense middleware for FestivaFlow.

Implements strict XSS sanitization, in-memory sliding-window rate limiting,
cryptographic token generation, and industry-standard security response headers.
"""

import hashlib
import html
import os
import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def sanitize_text(value: str | None) -> str | None:
    """Sanitize and HTML-escape string inputs to prevent Cross-Site Scripting (XSS).

    Args:
        value: Raw user-provided string or None.

    Returns:
        Escaped string with HTML meta-characters neutralized, or None.
    """
    if value is None:
        return None
    trimmed = value.strip()
    return html.escape(trimmed, quote=True)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces hardened OWASP-recommended HTTP response security headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Intercept response and inject security defense headers.

        Args:
            request: Incoming HTTP request.
            call_next: Next ASGI handler in middleware chain.

        Returns:
            Response: HTTP response fortified with security headers.
        """
        response: Response = await call_next(request)

        # Content-Security-Policy restricting untrusted scripts, frames, and objects
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Defend against MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking / frame embedding
        response.headers["X-Frame-Options"] = "DENY"

        # Strict referrer leakage control
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Enforce HTTPS transport policy
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Restrict dangerous browser features and sensors
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )

        return response


class SlidingWindowRateLimiter(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter per client IP address.

    Tracks timestamps of incoming requests within a rolling 60-second window.
    """

    def __init__(self, app, requests_per_minute: int = 100) -> None:
        """Initialize rate limiter with window configuration.

        Args:
            app: Starlette/FastAPI application instance.
            requests_per_minute: Maximum requests permitted per 60-second window.
        """
        super().__init__(app)
        self.requests_per_minute: int = int(
            os.getenv("RATE_LIMIT_PER_MINUTE", str(requests_per_minute))
        )
        self.window_seconds: float = 60.0
        self.requests_log: dict[str, list[float]] = {}
        self.rate_limiting_enabled: bool = (
            os.getenv("ENABLE_RATE_LIMIT", "true").lower() == "true"
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        """Evaluate request frequency against client IP window history.

        Args:
            request: Incoming HTTP request.
            call_next: Next ASGI handler.

        Returns:
            Response: Call outcome or 429 Too Many Requests JSON response.
        """
        # Bypass rate limiting if disabled or during specific internal test bypass
        if not self.rate_limiting_enabled or request.headers.get("X-Bypass-Rate-Limit") == "true":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown_client"
        now = time.time()

        # Clean old timestamps outside the sliding window
        timestamps = self.requests_log.setdefault(client_ip, [])
        threshold = now - self.window_seconds
        self.requests_log[client_ip] = [ts for ts in timestamps if ts > threshold]

        if len(self.requests_log[client_ip]) >= self.requests_per_minute:
            oldest_ts = self.requests_log[client_ip][0]
            retry_after = max(1, int(self.window_seconds - (now - oldest_ts)))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit of {self.requests_per_minute} requests per minute exceeded.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        self.requests_log[client_ip].append(now)
        return await call_next(request)


def generate_secure_token() -> str:
    """Generate a cryptographically secure URL-safe API authorization token.

    Returns:
        str: 32-byte high-entropy token string.
    """
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Compute the SHA-256 digest of an API token for safe storage.

    Args:
        raw_token: Plaintext token string.

    Returns:
        str: Hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

# Use client IP as the key for rate limiting.
# In production behind a proxy, use X-Forwarded-For — see limiter middleware setup in main.py.
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Convert RateLimitExceeded into a JSON 429 response."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "retry_after": getattr(exc, "retry_after", None),
        },
    )


# ── Rate limit definitions ──────────────────────────────────────
# Stricter limits for sensitive auth endpoints
LOGIN_RATE_LIMIT = "5/minute"
GOOGLE_LOGIN_RATE_LIMIT = "10/minute"
PASSWORD_RESET_RATE_LIMIT = "3/minute"
REGISTER_RATE_LIMIT = "5/minute"
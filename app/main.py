from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.db.database import Base, engine
from app.core.config import settings
from app.core.rate_limit import limiter
import app.models

# ── Startup security validations ───────────────────────────────
# Reject wildcard CORS origins when credentials are enabled —
# this is a critical misconfiguration that browsers block but we
# refuse to run with to make the problem explicit.
if "*" in settings.CORS_ORIGINS:
    raise ValueError(
        "CORS_ORIGINS contains '*' which is incompatible with allow_credentials=True. "
        "Set specific origins in CORS_ORIGINS environment variable."
    )

# create tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LMS Video Analysis API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Wire in rate limiter state and exception handler (must be after FastAPI instantiation)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "message": "LMS Video Analysis API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }

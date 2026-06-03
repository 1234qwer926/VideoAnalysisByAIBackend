from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.db.database import Base, engine
from app.core.config import settings
import app.models

# create tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LMS Video Analysis API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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

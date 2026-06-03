from fastapi import APIRouter
from app.api.routes import (
    admin_auth,
    candidate_auth,
    forms,
    assignments,
    submissions,
    results,
    candidate,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(admin_auth.router)
api_router.include_router(candidate_auth.router)
api_router.include_router(forms.router)
api_router.include_router(assignments.router)
api_router.include_router(submissions.router)
api_router.include_router(results.router)
api_router.include_router(candidate.router)
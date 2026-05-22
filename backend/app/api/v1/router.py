from __future__ import annotations
"""
ClinNote AI — API v1 Aggregated Router
=========================================
Aggregates all route modules into a single v1 router.
"""


from fastapi import APIRouter

from app.api.v1 import (
    auth,
    users,
    patients,
    recordings,
    consent,
    transcripts,
    notes,
    documents,
    fhir,
    icd,
    admin,
    websocket,
)
# Side-load Phase B+C voice-audit endpoints onto notes.router BEFORE include_router
from app.api.v1 import _phase_bc_endpoints  # noqa: F401

api_router = APIRouter()

# Include all sub-routers
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(patients.router)
api_router.include_router(recordings.router)
api_router.include_router(consent.router)
api_router.include_router(transcripts.router)
api_router.include_router(notes.router)
api_router.include_router(documents.router)
api_router.include_router(fhir.router)
api_router.include_router(icd.router)
api_router.include_router(admin.router)
# WebSocket router is included separately in main.py

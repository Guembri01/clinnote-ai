from __future__ import annotations
"""
ClinNote AI — Admin API
=========================
Admin-only endpoints for system monitoring and compliance reporting.

Endpoints:
  GET /admin/sessions    — List all recording sessions with stats
  GET /admin/audit-log   — Retrieve audit log entries (paginated)
  GET /admin/usage       — System usage statistics
"""


from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.v1.deps import DB, require_roles
from app.models.audit_log import AuditAction, AuditLog
from app.models.recording_session import RecordingSession, SessionStatus
from app.models.soap_note import NoteStatus, SOAPNote
from app.models.user import User, UserRole
from app.utils.encryption import get_phi_encryption
from sqlalchemy.orm import joinedload

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.get(
    "/stats",
    summary="System usage statistics for admin dashboard",
    description="Returns today's session/note counts and active physician count.",
)
async def get_stats(db: DB) -> dict:
    """Return UsageStats shape expected by AdminDashboard frontend component."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = now - timedelta(days=30)

    # Sessions today
    sessions_today_result = await db.execute(
        select(func.count(RecordingSession.id)).where(RecordingSession.created_at >= today_start)
    )
    sessions_today = sessions_today_result.scalar() or 0

    # Notes generated today
    notes_today_result = await db.execute(
        select(func.count(SOAPNote.id)).where(SOAPNote.created_at >= today_start)
    )
    notes_generated_today = notes_today_result.scalar() or 0

    # Pending approval (draft notes)
    pending_result = await db.execute(
        select(func.count(SOAPNote.id)).where(SOAPNote.status == NoteStatus.DRAFT)
    )
    pending_approval = pending_result.scalar() or 0

    # Active physicians (had at least one session in last 30 days)
    active_physicians_result = await db.execute(
        select(func.count(func.distinct(RecordingSession.user_id)))
        .where(RecordingSession.created_at >= period_start)
    )
    active_physicians = active_physicians_result.scalar() or 0

    # Totals
    total_sessions_result = await db.execute(select(func.count(RecordingSession.id)))
    total_sessions = total_sessions_result.scalar() or 0

    total_notes_result = await db.execute(select(func.count(SOAPNote.id)))
    total_notes = total_notes_result.scalar() or 0

    approved_result = await db.execute(
        select(func.count(SOAPNote.id)).where(SOAPNote.status == NoteStatus.APPROVED)
    )
    approved_notes = approved_result.scalar() or 0

    # Avg session duration
    avg_dur_result = await db.execute(
        select(func.avg(RecordingSession.duration_seconds)).where(
            RecordingSession.duration_seconds.isnot(None)
        )
    )
    avg_duration = int(avg_dur_result.scalar() or 0)

    return {
        "total_sessions": total_sessions,
        "total_notes": total_notes,
        "approved_notes": approved_notes,
        "pending_approval": pending_approval,
        "avg_session_duration_seconds": avg_duration,
        "sessions_today": sessions_today,
        "notes_generated_today": notes_generated_today,
        "active_physicians": active_physicians,
    }


@router.get(
    "/sessions/active",
    summary="List currently active recording sessions (admin)",
    description="Returns sessions in RECORDING or PAUSED status with physician info.",
)
async def get_active_sessions(db: DB) -> list:
    """Return ActiveSession list for live monitoring table."""
    result = await db.execute(
        select(RecordingSession, User)
        .join(User, RecordingSession.user_id == User.id, isouter=True)
        .where(RecordingSession.status.in_([SessionStatus.RECORDING, SessionStatus.PAUSED]))
        .order_by(RecordingSession.created_at.desc())
        .limit(100)
    )
    rows = result.all()

    enc = get_phi_encryption()

    def _mask_mrn(encrypted: str | None) -> str:
        if not encrypted:
            return "***"
        try:
            plain = enc.decrypt(encrypted) or ""
            return f"***{plain[-4:]}" if len(plain) >= 4 else "***"
        except Exception:
            return "***"

    return [
        {
            "session_id": str(session.id),
            "physician_name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "physician_id": str(session.user_id),
            "patient_mrn": _mask_mrn(session.patient_mrn),
            "status": session.status.value,
            "duration_seconds": session.duration_seconds or 0,
            "started_at": (
                session.start_time.isoformat() if session.start_time else session.created_at.isoformat()
            ),
        }
        for session, user in rows
    ]


@router.get(
    "/sessions",
    summary="List all recording sessions (admin)",
    description="Retrieve all recording sessions with summary statistics. Admin only.",
)
async def list_all_sessions(
    db: DB,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    status_filter: str | None = None,
    days_back: int = Query(default=30, description="Look back N days"),
) -> dict:
    """
    List all recording sessions across all users with statistics.

    Returns sessions within the specified lookback window.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days_back)

    stmt = (
        select(RecordingSession)
        .where(RecordingSession.created_at >= since)
        .order_by(RecordingSession.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if status_filter:
        try:
            stmt = stmt.where(RecordingSession.status == SessionStatus(status_filter))
        except ValueError:
            pass

    result = await db.execute(stmt)
    sessions = result.scalars().all()

    # Aggregate stats
    stats_result = await db.execute(
        select(
            RecordingSession.status,
            func.count(RecordingSession.id).label("count"),
        )
        .where(RecordingSession.created_at >= since)
        .group_by(RecordingSession.status)
    )
    stats = {row.status.value: row.count for row in stats_result}

    return {
        "sessions": [
            {
                "id": str(s.id),
                "user_id": str(s.user_id),
                "status": s.status.value,
                "duration_seconds": s.duration_seconds,
                "created_at": s.created_at.isoformat(),
                "audio_deleted": s.audio_deleted_at is not None,
            }
            for s in sessions
        ],
        "stats": stats,
        "period_days": days_back,
    }


@router.get(
    "/audit-log",
    summary="Retrieve HIPAA audit log (admin)",
    description=(
        "Retrieve paginated audit log entries for compliance reporting. "
        "patient_mrn fields are returned encrypted. Admin only."
    ),
)
async def get_audit_log(
    db: DB,
    page: int = 1,
    page_size: int = Query(default=50, le=500),
    skip: int = 0,
    limit: int = 0,
    user_id: str | None = None,
    action: str | None = None,
    days_back: int = Query(default=7, description="Look back N days"),
) -> dict:
    """
    Retrieve HIPAA audit log entries for compliance review.

    Returns PaginatedResponse<AuditLogEntry> shape for the frontend.
    PHI fields (patient_mrn) remain encrypted in the response.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days_back)

    # Support legacy skip/limit params
    if limit > 0:
        page_size = min(limit, 500)
        page = (skip // page_size) + 1 if page_size else 1

    page = max(1, page)
    page_size = min(max(1, page_size), 500)
    offset = (page - 1) * page_size

    base_stmt = select(AuditLog).where(AuditLog.timestamp >= since)
    if user_id:
        base_stmt = base_stmt.where(AuditLog.user_id == user_id)
    if action:
        try:
            base_stmt = base_stmt.where(AuditLog.action == AuditAction(action))
        except ValueError:
            pass

    total_result = await db.execute(select(func.count()).select_from(base_stmt.subquery()))
    total = total_result.scalar() or 0

    stmt = base_stmt.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    # Build user name map
    uid_set = {str(e.user_id) for e in entries if e.user_id}
    user_map: dict[str, str] = {}
    if uid_set:
        u_result = await db.execute(
            select(User.id, User.first_name, User.last_name, User.role).where(User.id.in_(uid_set))
        )
        for row in u_result:
            user_map[str(row.id)] = {
                "name": f"{row.first_name} {row.last_name}",
                "role": row.role.value if hasattr(row.role, "value") else str(row.role),
            }

    total_pages = max(1, (total + page_size - 1) // page_size)

    enc = get_phi_encryption()

    def _mask_mrn(encrypted: str | None) -> str | None:
        if not encrypted:
            return None
        try:
            plain = enc.decrypt(encrypted) or ""
            return f"***{plain[-4:]}" if len(plain) >= 4 else "***"
        except Exception:
            return "***"

    return {
        "data": [
            {
                "id": str(e.id),
                "action": e.action.value,
                "resource_type": e.resource_type or "",
                "resource_id": e.resource_id or "",
                "user_id": str(e.user_id) if e.user_id else None,
                "user_name": user_map.get(str(e.user_id), {}).get("name", "System") if e.user_id else "System",
                "user_role": user_map.get(str(e.user_id), {}).get("role", "") if e.user_id else "",
                "ip_address": e.ip_address or "",
                "user_agent": e.user_agent or "",
                "timestamp": e.timestamp.isoformat(),
                "details": {"text": e.details} if e.details else {},
                "phi_accessed": e.patient_mrn is not None,
                "patient_mrn": _mask_mrn(e.patient_mrn),
            }
            for e in entries
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


@router.get(
    "/usage",
    summary="System usage statistics (admin)",
    description="Dashboard statistics for system administrators.",
)
async def get_usage_stats(
    db: DB,
    days_back: int = Query(default=30),
) -> dict:
    """
    Return aggregated usage statistics for the admin dashboard.

    Includes:
    - Total recording sessions by status
    - Total SOAP notes by status
    - Active users
    - FHIR push success rate
    """
    since = datetime.now(timezone.utc) - timedelta(days=days_back)

    # Sessions by status
    sessions_result = await db.execute(
        select(RecordingSession.status, func.count(RecordingSession.id).label("count"))
        .where(RecordingSession.created_at >= since)
        .group_by(RecordingSession.status)
    )
    sessions_by_status = {row.status.value: row.count for row in sessions_result}

    # Notes by status
    notes_result = await db.execute(
        select(SOAPNote.status, func.count(SOAPNote.id).label("count"))
        .where(SOAPNote.created_at >= since)
        .group_by(SOAPNote.status)
    )
    notes_by_status = {row.status.value: row.count for row in notes_result}

    # Active users (users with at least one session)
    active_users_result = await db.execute(
        select(func.count(func.distinct(RecordingSession.user_id)))
        .where(RecordingSession.created_at >= since)
    )
    active_users = active_users_result.scalar() or 0

    # Total users
    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    total_users = total_users_result.scalar() or 0

    # FHIR push stats
    fhir_result = await db.execute(
        select(SOAPNote.fhir_push_status, func.count(SOAPNote.id).label("count"))
        .where(
            SOAPNote.fhir_push_status.isnot(None),
            SOAPNote.updated_at >= since,
        )
        .group_by(SOAPNote.fhir_push_status)
    )
    fhir_by_status = {row.fhir_push_status: row.count for row in fhir_result}

    fhir_total = sum(fhir_by_status.values())
    fhir_success_rate = (
        round(fhir_by_status.get("success", 0) / fhir_total * 100, 1) if fhir_total > 0 else 0.0
    )

    return {
        "period_days": days_back,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "users": {
            "total_active": total_users,
            "active_in_period": active_users,
        },
        "recording_sessions": sessions_by_status,
        "soap_notes": notes_by_status,
        "fhir_push": {
            **fhir_by_status,
            "success_rate_percent": fhir_success_rate,
        },
    }

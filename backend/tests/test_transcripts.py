from __future__ import annotations
"""
ClinNote AI — Transcript Endpoint Tests
=========================================
Tests for:
  - GET /transcripts/{session_id} — retrieve decrypted transcript
  - PATCH /transcripts/{id} — apply physician corrections
  - Ownership enforcement (only session owner or admin)
  - Transcript not yet available (404 before transcription)
  - Word count update on correction
"""


import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recording_session import RecordingSession, SessionStatus
from app.models.transcript import Transcript
from app.models.user import User
from app.utils.encryption import get_phi_encryption


# ---------------------------------------------------------------------------
# Helpers: seed session and transcript directly in DB
# ---------------------------------------------------------------------------
async def _seed_session(
    db: AsyncSession,
    user: User,
    status: SessionStatus = SessionStatus.COMPLETED,
) -> RecordingSession:
    enc = get_phi_encryption()
    session = RecordingSession(
        user_id=user.id,
        patient_mrn=enc.encrypt("MRN-TRANSCRIPT-TEST"),
        status=status,
    )
    db.add(session)
    await db.flush()
    return session


async def _seed_transcript(
    db: AsyncSession,
    session: RecordingSession,
    raw_text: str = "Patient presents with sore throat for three days.",
) -> Transcript:
    enc = get_phi_encryption()
    transcript = Transcript(
        session_id=session.id,
        raw_text=enc.encrypt(raw_text),
        corrected_text=enc.encrypt(raw_text),
        diarization=[{"speaker": "S1", "start": 0.0, "end": 4.0, "text": raw_text}],
        word_count=len(raw_text.split()),
        language="en",
        confidence=0.88,
    )
    db.add(transcript)
    await db.flush()
    return transcript


# ---------------------------------------------------------------------------
# GET /transcripts/{session_id}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestGetTranscript:
    """GET /api/v1/transcripts/{session_id}"""

    async def test_get_transcript_success(
        self,
        async_client: AsyncClient,
        physician_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Session owner can retrieve their transcript."""
        session = await _seed_session(db_session, physician_user)
        await _seed_transcript(db_session, session)

        response = await async_client.get(
            f"/api/v1/transcripts/{session.id}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "raw_text" in data
        assert data["raw_text"] == "Patient presents with sore throat for three days."
        assert data["language"] == "en"
        assert data["confidence"] == pytest.approx(0.88, abs=0.01)
        assert isinstance(data["diarization"], list)
        assert len(data["diarization"]) == 1
        assert data["diarization"][0]["speaker"] == "S1"

    async def test_get_transcript_not_yet_available_404(
        self,
        async_client: AsyncClient,
        physician_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Session with no transcript returns 404 with descriptive message."""
        session = await _seed_session(db_session, physician_user, status=SessionStatus.RECORDING)

        response = await async_client.get(
            f"/api/v1/transcripts/{session.id}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 404
        assert "in progress" in response.json()["detail"].lower() or "not yet" in response.json()["detail"].lower()

    async def test_get_transcript_session_not_found_404(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Non-existent session UUID returns 404."""
        response = await async_client.get(
            f"/api/v1/transcripts/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 404

    async def test_get_transcript_other_user_forbidden_403(
        self,
        async_client: AsyncClient,
        physician_token: str,
        nurse_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Another user's session transcript returns 403."""
        session = await _seed_session(db_session, physician_user)
        await _seed_transcript(db_session, session)

        response = await async_client.get(
            f"/api/v1/transcripts/{session.id}",
            headers={"Authorization": f"Bearer {nurse_token}"},
        )
        assert response.status_code == 403

    async def test_get_transcript_admin_can_access_any(
        self,
        async_client: AsyncClient,
        admin_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Admin can access any session's transcript."""
        session = await _seed_session(db_session, physician_user)
        await _seed_transcript(db_session, session)

        response = await async_client.get(
            f"/api/v1/transcripts/{session.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

    async def test_get_transcript_unauthenticated_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await async_client.get(f"/api/v1/transcripts/{uuid.uuid4()}")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /transcripts/{id}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestEditTranscript:
    """PATCH /api/v1/transcripts/{transcript_id}"""

    async def test_edit_transcript_success(
        self,
        async_client: AsyncClient,
        physician_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Physician can correct their transcript text."""
        session = await _seed_session(db_session, physician_user)
        transcript = await _seed_transcript(
            db_session, session,
            raw_text="Patience presents with sore throat."
        )

        corrected = "Patient presents with sore throat and mild fever."
        response = await async_client.patch(
            f"/api/v1/transcripts/{transcript.id}",
            json={"corrected_text": corrected},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["corrected_text"] == corrected
        assert data["word_count"] == len(corrected.split())

    async def test_edit_transcript_updates_word_count(
        self,
        async_client: AsyncClient,
        physician_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Word count should reflect the corrected text length."""
        session = await _seed_session(db_session, physician_user)
        transcript = await _seed_transcript(db_session, session, raw_text="Short text.")

        long_text = " ".join(["word"] * 50)
        response = await async_client.patch(
            f"/api/v1/transcripts/{transcript.id}",
            json={"corrected_text": long_text},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        assert response.json()["word_count"] == 50

    async def test_edit_transcript_not_found_404(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Editing a non-existent transcript returns 404."""
        response = await async_client.patch(
            f"/api/v1/transcripts/{uuid.uuid4()}",
            json={"corrected_text": "Updated text here."},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 404

    async def test_edit_transcript_empty_text_422(
        self,
        async_client: AsyncClient,
        physician_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Empty corrected_text should return 422."""
        session = await _seed_session(db_session, physician_user)
        transcript = await _seed_transcript(db_session, session)

        response = await async_client.patch(
            f"/api/v1/transcripts/{transcript.id}",
            json={"corrected_text": ""},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 422

    async def test_edit_transcript_unauthenticated_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated correction attempt returns 401."""
        response = await async_client.patch(
            f"/api/v1/transcripts/{uuid.uuid4()}",
            json={"corrected_text": "Some text."},
        )
        assert response.status_code == 401

    async def test_edit_transcript_other_user_forbidden_403(
        self,
        async_client: AsyncClient,
        physician_token: str,
        nurse_token: str,
        physician_user: User,
        db_session: AsyncSession,
    ) -> None:
        """Another user cannot edit the physician's transcript."""
        session = await _seed_session(db_session, physician_user)
        transcript = await _seed_transcript(db_session, session)

        response = await async_client.patch(
            f"/api/v1/transcripts/{transcript.id}",
            json={"corrected_text": "Unauthorized edit attempt."},
            headers={"Authorization": f"Bearer {nurse_token}"},
        )
        assert response.status_code == 403

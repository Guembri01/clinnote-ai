from __future__ import annotations
"""
ClinNote AI — Recording Session Tests
=======================================
Tests for:
  - Creating a recording session
  - Recording session lifecycle (consent → record → pause → resume → stop)
  - Consent recording
  - Access control (ownership enforcement)
  - Max duration validation
"""


import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.recording_session import RecordingSession, SessionStatus


@pytest.mark.asyncio
class TestCreateRecording:
    """Test POST /api/v1/recordings/start"""

    async def test_start_recording_as_physician(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Physician can start a new recording session."""
        response = await async_client.post(
            "/api/v1/recordings/start",
            json={"patient_mrn": "MRN-001234"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending_consent"
        assert "id" in data
        # MRN should be masked in response
        assert data["patient_mrn"] != "MRN-001234"

    async def test_start_recording_unauthenticated(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated request should return 401."""
        response = await async_client.post(
            "/api/v1/recordings/start",
            json={"patient_mrn": "MRN-001234"},
        )
        assert response.status_code == 401

    async def test_start_recording_missing_mrn(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Missing patient_mrn should return 422."""
        response = await async_client.post(
            "/api/v1/recordings/start",
            json={},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestConsentAndRecordingFlow:
    """Test the full recording session lifecycle."""

    async def test_consent_transitions_to_recording(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Recording consent should transition session to RECORDING status."""
        # Create session
        start_resp = await async_client.post(
            "/api/v1/recordings/start",
            json={"patient_mrn": "MRN-CONSENT-TEST"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert start_resp.status_code == 201
        session_id = start_resp.json()["id"]

        # Record consent
        consent_resp = await async_client.post(
            "/api/v1/consent/record",
            json={
                "session_id": session_id,
                "consent_type": "verbal",
                "notes": "Patient verbally confirmed",
            },
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert consent_resp.status_code == 200
        data = consent_resp.json()
        assert data["status"] == "recording"
        assert "consent_recorded_at" in data

    async def test_double_consent_fails(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Recording consent twice should fail with 409."""
        # Create session
        start_resp = await async_client.post(
            "/api/v1/recordings/start",
            json={"patient_mrn": "MRN-DOUBLE-CONSENT"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        session_id = start_resp.json()["id"]

        # First consent
        await async_client.post(
            "/api/v1/consent/record",
            json={"session_id": session_id, "consent_type": "verbal"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )

        # Second consent attempt
        second_consent = await async_client.post(
            "/api/v1/consent/record",
            json={"session_id": session_id, "consent_type": "verbal"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert second_consent.status_code == 409

    async def test_full_lifecycle(
        self,
        async_client: AsyncClient,
        physician_token: str,
        mock_redis,
    ) -> None:
        """Test start → consent → pause → resume → stop."""
        # Start
        start_resp = await async_client.post(
            "/api/v1/recordings/start",
            json={"patient_mrn": "MRN-LIFECYCLE"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        session_id = start_resp.json()["id"]

        # Consent
        await async_client.post(
            "/api/v1/consent/record",
            json={"session_id": session_id, "consent_type": "verbal"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )

        # Pause
        pause_resp = await async_client.post(
            f"/api/v1/recordings/{session_id}/pause",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert pause_resp.status_code == 200
        assert pause_resp.json()["status"] == "paused"

        # Resume
        resume_resp = await async_client.post(
            f"/api/v1/recordings/{session_id}/resume",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["status"] == "recording"

        # Stop (mocked celery task)
        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "app.workers.transcription_tasks.process_final_transcript"
        ):
            stop_resp = await async_client.post(
                f"/api/v1/recordings/{session_id}/stop",
                headers={"Authorization": f"Bearer {physician_token}"},
            )
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "completed"


@pytest.mark.asyncio
class TestAccessControl:
    """Test that users can only access their own sessions."""

    async def test_nurse_cannot_access_physician_session(
        self,
        async_client: AsyncClient,
        physician_token: str,
        nurse_token: str,
    ) -> None:
        """A nurse cannot access another clinician's session."""
        # Physician creates session
        start_resp = await async_client.post(
            "/api/v1/recordings/start",
            json={"patient_mrn": "MRN-RBAC-TEST"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        session_id = start_resp.json()["id"]

        # Nurse tries to access it
        get_resp = await async_client.get(
            f"/api/v1/recordings/{session_id}",
            headers={"Authorization": f"Bearer {nurse_token}"},
        )
        assert get_resp.status_code == 403

    async def test_admin_can_access_any_session(
        self,
        async_client: AsyncClient,
        physician_token: str,
        admin_token: str,
    ) -> None:
        """Admin can access any session."""
        # Physician creates session
        start_resp = await async_client.post(
            "/api/v1/recordings/start",
            json={"patient_mrn": "MRN-ADMIN-ACCESS"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        session_id = start_resp.json()["id"]

        # Admin accesses it
        get_resp = await async_client.get(
            f"/api/v1/recordings/{session_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 200

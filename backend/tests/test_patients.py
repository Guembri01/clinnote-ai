from __future__ import annotations
"""
ClinNote AI — Patient Endpoint Tests
=======================================
Tests for:
  - POST /patients — create patient with encrypted PHI
  - GET  /patients — list patients (paginated)
  - GET  /patients/{id} — get patient by UUID
  - GET  /patients/mrn/{mrn} — get patient by MRN (HMAC lookup)
  - Access control enforcement (clinical staff only)
  - Duplicate MRN rejection (409)
"""


import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.user import User
from app.utils.encryption import get_phi_encryption, compute_hmac
from app.config import get_settings


# ---------------------------------------------------------------------------
# Helper: seed a patient directly in the DB
# ---------------------------------------------------------------------------
async def _seed_patient(
    db: AsyncSession,
    mrn: str = "MRN-SEED-001",
    first_name: str = "Jane",
    last_name: str = "Doe",
) -> Patient:
    enc = get_phi_encryption()
    settings = get_settings()
    patient = Patient(
        mrn=enc.encrypt(mrn),
        mrn_hmac=compute_hmac(mrn, settings.ENCRYPTION_KEY or ""),
        enc_first_name=enc.encrypt(first_name),
        enc_last_name=enc.encrypt(last_name),
        enc_dob=enc.encrypt("1985-03-22"),
        org_id="test-org",
    )
    db.add(patient)
    await db.flush()
    return patient


# ---------------------------------------------------------------------------
# POST /patients
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestCreatePatient:
    """POST /api/v1/patients"""

    async def test_create_patient_success(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Clinical staff can create a patient record."""
        response = await async_client.post(
            "/api/v1/patients",
            json={
                "mrn": f"MRN-NEW-{uuid.uuid4().hex[:6]}",
                "first_name": "Alice",
                "last_name": "Smith",
                "dob": "1990-06-15",
            },
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Alice"
        assert data["last_name"] == "Smith"
        assert data["dob"] == "1990-06-15"
        assert "id" in data

    async def test_create_patient_minimal_fields(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Creating a patient with only MRN should succeed."""
        response = await async_client.post(
            "/api/v1/patients",
            json={"mrn": f"MRN-MIN-{uuid.uuid4().hex[:6]}"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["first_name"] is None
        assert data["last_name"] is None

    async def test_create_patient_missing_mrn_422(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Missing MRN should return 422."""
        response = await async_client.post(
            "/api/v1/patients",
            json={"first_name": "John"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 422

    async def test_create_patient_duplicate_mrn_409(
        self,
        async_client: AsyncClient,
        physician_token: str,
        db_session: AsyncSession,
    ) -> None:
        """Duplicate MRN should return 409 Conflict."""
        mrn = f"MRN-DUP-{uuid.uuid4().hex[:6]}"
        await _seed_patient(db_session, mrn=mrn)

        response = await async_client.post(
            "/api/v1/patients",
            json={"mrn": mrn, "first_name": "Bob"},
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 409
        assert "MRN" in response.json()["detail"]

    async def test_create_patient_unauthenticated_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated request should return 401."""
        response = await async_client.post(
            "/api/v1/patients",
            json={"mrn": "MRN-UNAUTH"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /patients
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestListPatients:
    """GET /api/v1/patients"""

    async def test_list_patients_returns_200(
        self,
        async_client: AsyncClient,
        physician_token: str,
        db_session: AsyncSession,
    ) -> None:
        """Clinical staff can list patients."""
        await _seed_patient(db_session, mrn=f"MRN-LIST-{uuid.uuid4().hex[:6]}")

        response = await async_client.get(
            "/api/v1/patients",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_list_patients_pagination(
        self,
        async_client: AsyncClient,
        physician_token: str,
        db_session: AsyncSession,
    ) -> None:
        """List endpoint respects limit and skip parameters."""
        for i in range(3):
            await _seed_patient(db_session, mrn=f"MRN-PAGE-{uuid.uuid4().hex[:6]}")

        response = await async_client.get(
            "/api/v1/patients?limit=1&skip=0",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 1

    async def test_list_patients_unauthenticated_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated request to list patients returns 401."""
        response = await async_client.get("/api/v1/patients")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /patients/{id}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestGetPatientById:
    """GET /api/v1/patients/{patient_id}"""

    async def test_get_patient_by_id_success(
        self,
        async_client: AsyncClient,
        physician_token: str,
        db_session: AsyncSession,
    ) -> None:
        """Clinical staff can retrieve a patient by UUID."""
        patient = await _seed_patient(
            db_session,
            mrn=f"MRN-GET-{uuid.uuid4().hex[:6]}",
            first_name="Carol",
            last_name="Johnson",
        )

        response = await async_client.get(
            f"/api/v1/patients/{patient.id}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Carol"
        assert data["last_name"] == "Johnson"
        assert str(data["id"]) == str(patient.id)

    async def test_get_patient_by_id_not_found_404(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Non-existent patient UUID should return 404."""
        response = await async_client.get(
            f"/api/v1/patients/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 404

    async def test_get_patient_unauthenticated_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated access should return 401."""
        response = await async_client.get(f"/api/v1/patients/{uuid.uuid4()}")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /patients/mrn/{mrn}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestGetPatientByMRN:
    """GET /api/v1/patients/mrn/{mrn}"""

    async def test_get_patient_by_mrn_success(
        self,
        async_client: AsyncClient,
        physician_token: str,
        db_session: AsyncSession,
    ) -> None:
        """HMAC-based MRN lookup returns the correct patient."""
        mrn = f"MRN-HMAC-{uuid.uuid4().hex[:6]}"
        patient = await _seed_patient(db_session, mrn=mrn, first_name="David")

        response = await async_client.get(
            f"/api/v1/patients/mrn/{mrn}",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert str(data["id"]) == str(patient.id)
        assert data["first_name"] == "David"

    async def test_get_patient_by_mrn_not_found_404(
        self,
        async_client: AsyncClient,
        physician_token: str,
    ) -> None:
        """Unknown MRN should return 404."""
        response = await async_client.get(
            "/api/v1/patients/mrn/MRN-UNKNOWN-XYZ",
            headers={"Authorization": f"Bearer {physician_token}"},
        )
        assert response.status_code == 404

    async def test_get_patient_by_mrn_unauthenticated_401(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated MRN lookup should return 401."""
        response = await async_client.get("/api/v1/patients/mrn/MRN-001")
        assert response.status_code == 401

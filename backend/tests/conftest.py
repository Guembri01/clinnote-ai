"""
ClinNote AI — Test Configuration and Fixtures
===============================================
Pytest fixtures for:
  - In-memory SQLite async database (aiosqlite)
  - Test FastAPI client
  - Pre-seeded test users (admin, physician, nurse)
  - Mocked OpenAI and DeepInfra clients
  - Test JWT tokens
"""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-minimum-32-chars-ok!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


import asyncio
import types
import uuid

# Override DATABASE_URL to SQLite before any app module imports

# bcrypt 4.x removed __about__; patch before passlib imports it
try:
    import bcrypt as _bcrypt
    if not hasattr(_bcrypt, '__about__'):
        _bcrypt.__about__ = types.SimpleNamespace(__version__=_bcrypt.__version__)
except ImportError:
    pass
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.utils.encryption import PHIEncryption
import importlib as _il; _il.import_module("app.workers.transcription_tasks")  # needed so patch() resolves app.workers attr chain

# ---------------------------------------------------------------------------
# Test database (SQLite in-memory via aiosqlite)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create all tables in the in-memory test database once per session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test database session that rolls back after each test."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.rollback()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture
def override_get_db(db_session: AsyncSession):
    """Override the get_db dependency to use the test database."""
    async def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test encryption (deterministic key for tests)
# ---------------------------------------------------------------------------
TEST_ENCRYPTION_KEY = "O2bMuNwH91mxqPUMG5lbA5a1bwz2KFW_tXqlp1zNlYk="


@pytest.fixture(autouse=True)
def patch_encryption(monkeypatch):
    """Patch encryption to use a test key."""
    test_enc = PHIEncryption(key=TEST_ENCRYPTION_KEY)
    with patch("app.utils.encryption.get_phi_encryption", return_value=test_enc):
        yield test_enc


# ---------------------------------------------------------------------------
# Test users
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create and return an admin user."""
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"admin-{uid[:8]}@example.com",
        hashed_password=AuthService.hash_password("AdminPass!123"),
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        is_active=True,
        org_id="test-org",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def physician_user(db_session: AsyncSession) -> User:
    """Create and return a physician user with specialty."""
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"dr.jones-{uid[:8]}@example.com",
        hashed_password=AuthService.hash_password("DoctorPass!123"),
        first_name="Sarah",
        last_name="Jones",
        role=UserRole.PHYSICIAN,
        specialty="primary_care",
        npi_number=uid[:10],
        is_active=True,
        org_id="test-org",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def nurse_user(db_session: AsyncSession) -> User:
    """Create and return a nurse user."""
    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"nurse.smith-{uid[:8]}@example.com",
        hashed_password=AuthService.hash_password("NursePass!123"),
        first_name="Bob",
        last_name="Smith",
        role=UserRole.NURSE,
        is_active=True,
        org_id="test-org",
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ---------------------------------------------------------------------------
# JWT token helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Return a valid JWT access token for the admin user."""
    token, _ = AuthService.create_access_token(
        user_id=str(admin_user.id),
        email=admin_user.email,
        role=admin_user.role.value,
    )
    return token


@pytest.fixture
def physician_token(physician_user: User) -> str:
    """Return a valid JWT access token for the physician user."""
    token, _ = AuthService.create_access_token(
        user_id=str(physician_user.id),
        email=physician_user.email,
        role=physician_user.role.value,
    )
    return token


@pytest.fixture
def nurse_token(nurse_user: User) -> str:
    """Return a valid JWT access token for the nurse user."""
    token, _ = AuthService.create_access_token(
        user_id=str(nurse_user.id),
        email=nurse_user.email,
        role=nurse_user.role.value,
    )
    return token


# ---------------------------------------------------------------------------
# HTTP Test Client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def async_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for FastAPI."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
def sync_client(override_get_db) -> Generator[TestClient, None, None]:
    """Synchronous test client for FastAPI."""
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Mocked AI service clients
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_openai():
    """Mock AsyncOpenAI client to avoid real API calls in tests."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "subjective": "Patient presents with 3-day history of sore throat",
        "objective": "Temp 38.2C, BP 122/78, HR 88, throat erythematous",
        "assessment": "1. Acute pharyngitis (J02.9)",
        "plan": "1. Rapid strep test\\n2. Acetaminophen 500mg q6h PRN",
        "icd10_codes": [{"code": "J02.9", "description": "Acute pharyngitis, unspecified", "confidence": 0.92, "is_primary": true}],
        "cpt_codes": [{"code": "99213", "description": "Office visit, established patient, moderate complexity", "confidence": 0.85}]
    }"""

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.services.soap_service.AsyncOpenAI", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_deepinfra():
    """Mock httpx client for DeepInfra Whisper to avoid real API calls."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "text": "Patient presents with sore throat for three days.",
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "Patient presents with sore throat", "avg_logprob": -0.3},
            {"start": 2.5, "end": 4.0, "text": "for three days.", "avg_logprob": -0.2},
        ],
    }
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.transcription_service.httpx.AsyncClient") as mock_httpx:
        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_redis():
    """Mock Redis client for tests."""
    mock_redis_client = AsyncMock()
    mock_redis_client.get = AsyncMock(return_value=b"fake_audio_data")
    mock_redis_client.set = AsyncMock(return_value=True)
    mock_redis_client.setex = AsyncMock(return_value=True)
    mock_redis_client.delete = AsyncMock(return_value=1)
    mock_redis_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_redis_client):
        yield mock_redis_client

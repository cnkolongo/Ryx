"""Tests unitaires gateway auth — login, refresh token, create user.

Utilise SQLite en mémoire pour les tests sans PostgreSQL.
"""

import sys
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

sys.path.insert(0, str(Path(__file__).parents[4] / "packages" / "shared"))

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    from app.database import Base
    import app.models  # noqa: F401 — registers all ORM models with Base.metadata
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_engine):
    import app.database as db_module
    from app.main import app
    from app.database import get_db

    # Remplacer l'engine de prod par le test engine
    original_engine = db_module.engine
    db_module.engine = test_engine

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    db_module.engine = original_engine


async def create_test_user(client, username="testdoc", password="Secret123!", role="doctor"):
    """Helper : créer un utilisateur de test."""
    resp = await client.post("/v1/auth/users", json={
        "username": username,
        "password": password,
        "role": role,
    })
    assert resp.status_code == 201, f"Create user failed: {resp.text}"
    return resp.json()


# ─── Tests création utilisateur ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreateUser:
    async def test_create_user_success(self, client):
        resp = await client.post("/v1/auth/users", json={
            "username": "jean_paul",
            "password": "SecurePass!99",
            "role": "doctor",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "jean_paul"
        assert data["role"] == "doctor"
        assert "user_id" in data
        assert "password" not in data  # jamais retourner le mot de passe

    async def test_create_user_duplicate_username(self, client):
        await create_test_user(client, username="dup_user")
        resp = await client.post("/v1/auth/users", json={
            "username": "dup_user",
            "password": "AnotherPass!",
        })
        assert resp.status_code == 409

    async def test_create_user_default_role_doctor(self, client):
        resp = await client.post("/v1/auth/users", json={
            "username": "nurse_test",
            "password": "NursePass!",
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "doctor"  # default


# ─── Tests login ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client):
        await create_test_user(client, username="doc1", password="DocPass!99")
        resp = await client.post("/v1/auth/token", json={
            "username": "doc1",
            "password": "DocPass!99",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    async def test_login_wrong_password(self, client):
        await create_test_user(client, username="doc2", password="Correct!")
        resp = await client.post("/v1/auth/token", json={
            "username": "doc2",
            "password": "Wrong!",
        })
        assert resp.status_code == 401

    async def test_login_unknown_user(self, client):
        resp = await client.post("/v1/auth/token", json={
            "username": "nobody",
            "password": "Whatever!",
        })
        assert resp.status_code == 401

    async def test_login_returns_jwt_with_correct_claims(self, client):
        """Vérifier que le JWT contient les bons claims."""
        from jose import jwt as jose_jwt
        from ryx_shared.config import RyxConfig
        config = RyxConfig()

        await create_test_user(client, username="doc3", password="Pass!99", role="doctor")
        resp = await client.post("/v1/auth/token", json={
            "username": "doc3", "password": "Pass!99"
        })
        token = resp.json()["access_token"]
        payload = jose_jwt.decode(token, config.jwt_secret_key, algorithms=[config.jwt_algorithm])
        assert payload["role"] == "doctor"
        assert payload["type"] == "access"
        assert "sub" in payload
        assert "exp" in payload


# ─── Tests /auth/me ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetMe:
    async def test_get_me_authenticated(self, client):
        await create_test_user(client, username="me_user", password="MePass!")
        login = await client.post("/v1/auth/token", json={
            "username": "me_user", "password": "MePass!"
        })
        token = login.json()["access_token"]

        resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "me_user"
        assert data["role"] == "doctor"

    async def test_get_me_no_token_401(self, client):
        resp = await client.get("/v1/auth/me")
        assert resp.status_code in (401, 403)

    async def test_get_me_invalid_token_401(self, client):
        resp = await client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401


# ─── Tests refresh token ──────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRefreshToken:
    async def test_refresh_token_success(self, client):
        await create_test_user(client, username="refresh_user", password="RefreshPass!")
        login = await client.post("/v1/auth/token", json={
            "username": "refresh_user", "password": "RefreshPass!"
        })
        refresh_token = login.json()["refresh_token"]

        resp = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_token_rotated(self, client):
        """Le refresh token doit être invalidé après utilisation (rotation)."""
        await create_test_user(client, username="rotate_user", password="RotatePass!")
        login = await client.post("/v1/auth/token", json={
            "username": "rotate_user", "password": "RotatePass!"
        })
        old_refresh = login.json()["refresh_token"]

        # Premier refresh → OK
        await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})

        # Deuxième refresh avec l'ancien token → doit échouer (révoqué)
        resp2 = await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
        assert resp2.status_code == 401

    async def test_refresh_invalid_token(self, client):
        resp = await client.post("/v1/auth/refresh", json={"refresh_token": "invalid.token"})
        assert resp.status_code == 401


# ─── Tests password hashing ───────────────────────────────────────────────────

class TestPasswordHashing:
    """Tests unitaires purs — pas de DB."""

    def test_hash_is_not_plaintext(self):
        from app.auth import hash_password
        hashed = hash_password("MySecret!")
        assert hashed != "MySecret!"
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        from app.auth import hash_password, verify_password
        hashed = hash_password("MySecret!")
        assert verify_password("MySecret!", hashed) is True

    def test_verify_wrong_password(self):
        from app.auth import hash_password, verify_password
        hashed = hash_password("MySecret!")
        assert verify_password("WrongPass", hashed) is False

    def test_same_password_different_hashes(self):
        """bcrypt doit générer des hashes différents (salt aléatoire)."""
        from app.auth import hash_password
        h1 = hash_password("SamePass!")
        h2 = hash_password("SamePass!")
        assert h1 != h2


# ─── Tests JWT ────────────────────────────────────────────────────────────────

class TestJWT:
    def test_create_and_decode_access_token(self):
        from app.auth import create_access_token, decode_token, Role
        user_id = uuid4()
        token = create_access_token(user_id, Role.DOCTOR)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "doctor"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        from app.auth import create_refresh_token, decode_token
        user_id = uuid4()
        token = create_refresh_token(user_id)
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

import pytest
import time
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import os
os.environ["TESTING"] = "1"
from app.main import app
from app.db.session import get_session
from app.config import settings

def make_engine():
    return create_async_engine(settings.database_url, poolclass=NullPool)

async def override_get_session():
    engine = make_engine()
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()

app.dependency_overrides[get_session] = override_get_session

@pytest.fixture()
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        timeout=30.0
    ) as c:
        yield c

@pytest.fixture()
async def auth_headers(client):
    uid = str(int(time.time() * 1000))
    username = f"testuser_{uid}"
    email = f"test_{uid}@test.com"
    await client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": "TestPass1234!"
    })
    resp = await client.post("/auth/login", data={
        "username": username,
        "password": "TestPass1234!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

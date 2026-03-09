import pytest

pytestmark = pytest.mark.asyncio

async def test_register_success(client):
    import time
    uid = str(int(time.time()))
    resp = await client.post("/auth/register", json={
        "username": f"newuser{uid}", "email": f"new{uid}@test.com", "password": "Test1234!"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "username" in data
    assert "id" in data

async def test_register_duplicate_username(client):
    payload = {"username": "dupuser", "email": "dup@test.com", "password": "Test1234!"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json={
        "username": "dupuser", "email": "dup2@test.com", "password": "Test1234!"
    })
    assert resp.status_code in (400, 409)

async def test_register_duplicate_email(client):
    await client.post("/auth/register", json={
        "username": "emailuser1", "email": "same@test.com", "password": "Test1234!"
    })
    resp = await client.post("/auth/register", json={
        "username": "emailuser2", "email": "same@test.com", "password": "Test1234!"
    })
    assert resp.status_code in (400, 409)

async def test_login_success(client):
    await client.post("/auth/register", json={
        "username": "loginuser", "email": "login@test.com", "password": "Test1234!"
    })
    resp = await client.post("/auth/login", data={
        "username": "loginuser", "password": "Test1234!"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"

async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "username": "wrongpass", "email": "wrongpass@test.com", "password": "Test1234!"
    })
    resp = await client.post("/auth/login", data={
        "username": "wrongpass", "password": "WrongPassword!"
    })
    assert resp.status_code == 401

async def test_login_nonexistent_user(client):
    resp = await client.post("/auth/login", data={
        "username": "ghostuser", "password": "Test1234!"
    })
    assert resp.status_code == 401

async def test_get_me_authenticated(client, auth_headers):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert "username" in resp.json()

async def test_get_me_unauthenticated(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401

async def test_get_me_invalid_token(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401

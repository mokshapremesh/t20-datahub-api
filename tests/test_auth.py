import pytest
import time

pytestmark = pytest.mark.asyncio

def uid():
    return str(int(time.time() * 1000))

async def test_register_success(client):
    u = uid()
    resp = await client.post("/auth/register", json={
        "username": f"newuser{u}", "email": f"new{u}@test.com", "password": "TestPass1234!"
    })
    assert resp.status_code == 201
    assert "username" in resp.json()

async def test_register_duplicate_username(client):
    u = uid()
    await client.post("/auth/register", json={
        "username": f"dup{u}", "email": f"dup{u}@test.com", "password": "TestPass1234!"
    })
    resp = await client.post("/auth/register", json={
        "username": f"dup{u}", "email": f"dup2{u}@test.com", "password": "TestPass1234!"
    })
    assert resp.status_code in (400, 409)

async def test_register_duplicate_email(client):
    u = uid()
    await client.post("/auth/register", json={
        "username": f"em1{u}", "email": f"same{u}@test.com", "password": "TestPass1234!"
    })
    resp = await client.post("/auth/register", json={
        "username": f"em2{u}", "email": f"same{u}@test.com", "password": "TestPass1234!"
    })
    assert resp.status_code in (400, 409)

async def test_register_weak_password(client):
    u = uid()
    resp = await client.post("/auth/register", json={
        "username": f"weak{u}", "email": f"weak{u}@test.com", "password": "short"
    })
    assert resp.status_code == 400

async def test_register_no_number_in_password(client):
    u = uid()
    resp = await client.post("/auth/register", json={
        "username": f"nonum{u}", "email": f"nonum{u}@test.com", "password": "onlylettershere"
    })
    assert resp.status_code == 400

async def test_login_success(client):
    u = uid()
    await client.post("/auth/register", json={
        "username": f"login{u}", "email": f"login{u}@test.com", "password": "TestPass1234!"
    })
    resp = await client.post("/auth/login", data={
        "username": f"login{u}", "password": "TestPass1234!"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

async def test_login_wrong_password(client):
    u = uid()
    await client.post("/auth/register", json={
        "username": f"wp{u}", "email": f"wp{u}@test.com", "password": "TestPass1234!"
    })
    resp = await client.post("/auth/login", data={
        "username": f"wp{u}", "password": "WrongPassword1234!"
    })
    assert resp.status_code == 401

async def test_login_nonexistent_user(client):
    resp = await client.post("/auth/login", data={
        "username": "ghostuser99999", "password": "TestPass1234!"
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

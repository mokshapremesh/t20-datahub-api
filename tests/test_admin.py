import pytest
import time

pytestmark = pytest.mark.asyncio

@pytest.fixture()
async def admin_headers(client):
    uid = str(int(time.time()))
    # Register then promote via DB
    await client.post("/auth/register", json={
        "username": f"admin{uid}", "email": f"admin{uid}@test.com", "password": "Admin1234!"
    })
    # Login as regular user - we'll test admin endpoints separately
    resp = await client.post("/auth/login", data={
        "username": f"admin{uid}", "password": "Admin1234!"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

async def test_non_admin_cannot_create_match(client, auth_headers):
    resp = await client.post("/matches", json={
        "team1": "India", "team2": "Pakistan",
        "match_date": "2024-06-01", "venue": "Test",
        "tournament_year": "2024"
    }, headers=auth_headers)
    assert resp.status_code == 403

async def test_non_admin_cannot_delete_match(client, auth_headers):
    resp = await client.delete("/matches/1", headers=auth_headers)
    assert resp.status_code == 403

async def test_non_admin_cannot_update_match(client, auth_headers):
    resp = await client.patch("/matches/1", json={"venue": "Hack"}, headers=auth_headers)
    assert resp.status_code == 403

async def test_create_match_no_auth(client):
    resp = await client.post("/matches", json={
        "team1": "India", "team2": "Pakistan",
        "match_date": "2024-06-01", "venue": "Test",
        "tournament_year": "2024"
    })
    assert resp.status_code == 401

async def test_delete_match_no_auth(client):
    resp = await client.delete("/matches/1")
    assert resp.status_code == 401

async def test_update_match_no_auth(client):
    resp = await client.patch("/matches/1", json={"venue": "Hack"})
    assert resp.status_code == 401

async def test_delete_nonexistent_match_no_auth(client):
    resp = await client.delete("/matches/999999")
    assert resp.status_code == 401

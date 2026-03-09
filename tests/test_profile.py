import pytest

pytestmark = pytest.mark.asyncio

async def test_upsert_profile_creates(client, auth_headers):
    resp = await client.put(
        "/me/profile?display_name=TestUser&fav_team=India&fav_player_key=V Kohli&fav_year=2024",
        headers=auth_headers
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["profile"]["display_name"] == "TestUser"
    assert data["profile"]["fav_team"]["key"] == "India" or data["profile"]["fav_team"] == "India"

async def test_upsert_profile_updates(client, auth_headers):
    await client.put("/me/profile?display_name=Original", headers=auth_headers)
    resp = await client.put("/me/profile?display_name=Updated", headers=auth_headers)
    assert resp.status_code in (200, 201)
    assert resp.json()["profile"]["display_name"] == "Updated"

async def test_get_profile_authenticated(client, auth_headers):
    await client.put("/me/profile?display_name=TestUser", headers=auth_headers)
    resp = await client.get("/me/profile", headers=auth_headers)
    assert resp.status_code == 200

async def test_get_profile_unauthenticated(client):
    resp = await client.get("/me/profile")
    assert resp.status_code == 401

async def test_get_dashboard(client, auth_headers):
    resp = await client.get("/me/dashboard", headers=auth_headers)
    assert resp.status_code == 200

async def test_delete_profile(client):
    # Register a fresh user for deletion test
    await client.post("/auth/register", json={
        "username": "deleteuser", "email": "delete@test.com", "password": "Test1234!"
    })
    login = await client.post("/auth/login", data={
        "username": "deleteuser", "password": "Test1234!"
    })
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    await client.put("/me/profile?display_name=ToDelete", headers=headers)
    resp = await client.delete("/me/profile", headers=headers)
    assert resp.status_code == 204

async def test_profile_unauthenticated_put(client):
    resp = await client.put("/me/profile?display_name=hacker")
    assert resp.status_code == 401

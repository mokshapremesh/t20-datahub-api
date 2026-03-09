import pytest

pytestmark = pytest.mark.asyncio

@pytest.fixture()
async def match_id(client):
    resp = await client.get("/matches?year=2024")
    matches = resp.json()["matches"]
    assert len(matches) > 0, "No matches found for 2024"
    return matches[0]["id"]

@pytest.fixture()
async def squad(client, match_id):
    resp = await client.get(f"/matches/{match_id}/squads")
    assert resp.status_code == 200
    data = resp.json()
    # find the squads list - could be under different key
    # players is a dict keyed by team name, values are lists of player dicts
    all_players = []
    for key, val in data.get("players", {}).items():
        if isinstance(val, list):
            for p in val:
                if isinstance(p, dict) and "player_key" in p:
                    all_players.append(p["player_key"])
    return all_players[:11], match_id

async def test_get_squads(client, match_id):
    resp = await client.get(f"/matches/{match_id}/squads")
    assert resp.status_code == 200
    data = resp.json()
    assert "players" in data
    assert len(data["players"]) > 0

async def test_get_squads_invalid_match(client):
    resp = await client.get("/matches/999999/squads")
    assert resp.status_code == 404

async def test_create_fantasy_team(client, auth_headers, squad):
    players, mid = squad
    params = [("name", "TestTeam")] + [("player_keys", p) for p in players]
    resp = await client.post(
        f"/matches/{mid}/fantasy/teams",
        params=params,
        headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert len(data["player_keys"]) == 11

async def test_create_team_unauthenticated(client, match_id):
    resp = await client.post(f"/matches/{match_id}/fantasy/teams?name=Hack")
    assert resp.status_code == 401

async def test_list_fantasy_teams(client, auth_headers, match_id):
    resp = await client.get(f"/matches/{match_id}/fantasy/teams", headers=auth_headers)
    assert resp.status_code == 200
    assert "teams" in resp.json()

async def test_match_leaderboard(client, match_id):
    resp = await client.get(f"/matches/{match_id}/fantasy/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "leaderboard" in data
    assert data["match_id"] == match_id

async def test_global_leaderboard(client):
    resp = await client.get("/fantasy/leaderboard?year=2024")
    assert resp.status_code == 200
    assert "leaderboard" in resp.json()

async def test_global_leaderboard_no_year(client):
    resp = await client.get("/fantasy/leaderboard")
    assert resp.status_code == 200

async def test_get_team_not_found(client, auth_headers):
    resp = await client.get("/fantasy/teams/999999", headers=auth_headers)
    assert resp.status_code == 404

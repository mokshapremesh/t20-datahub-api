import pytest

pytestmark = pytest.mark.asyncio

async def test_get_teams_no_filter(client):
    resp = await client.get("/options/teams")
    assert resp.status_code == 200
    data = resp.json()
    assert "teams" in data
    assert "total" in data

async def test_get_teams_year_filter(client):
    resp = await client.get("/options/teams?year=2024")
    assert resp.status_code == 200
    data = resp.json()
    assert data["filter"]["year"] == "2024"

async def test_get_teams_has_win_loss(client):
    resp = await client.get("/options/teams?year=2024")
    assert resp.status_code == 200
    teams = resp.json()["teams"]
    if teams:
        team = teams[0]
        assert "wins" in team
        assert "losses" in team
        assert "win_rate" in team

async def test_get_teams_tournament_winner(client):
    resp = await client.get("/options/teams?year=2024")
    assert resp.status_code == 200
    assert "tournament_winner" in resp.json()

async def test_get_teams_all_years(client):
    for year in ["2014", "2016", "2021", "2022", "2024"]:
        resp = await client.get(f"/options/teams?year={year}")
        assert resp.status_code == 200

async def test_get_players_no_filter(client):
    resp = await client.get("/options/players")
    assert resp.status_code == 200
    data = resp.json()
    assert "players" in data

async def test_get_players_team_filter(client):
    resp = await client.get("/options/players?team=India")
    assert resp.status_code == 200
    players = resp.json()["players"]
    if players:
        for p in players:
            assert p["team"] == "India"

async def test_get_players_search(client):
    resp = await client.get("/options/players?search=Kohli")
    assert resp.status_code == 200
    players = resp.json()["players"]
    if players:
        assert any("Kohli" in p["player_key"] for p in players)

async def test_get_players_year_filter(client):
    resp = await client.get("/options/players?year=2024")
    assert resp.status_code == 200
    assert "players" in resp.json()

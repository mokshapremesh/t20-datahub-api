import pytest

pytestmark = pytest.mark.asyncio

async def test_list_matches_returns_200(client):
    resp = await client.get("/matches")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "matches" in data
    assert isinstance(data["matches"], list)

async def test_list_matches_team_filter(client):
    resp = await client.get("/matches?team=India")
    assert resp.status_code == 200
    data = resp.json()
    for match in data["matches"]:
        assert "India" in (match["team1"] or "") or "India" in (match["team2"] or "")

async def test_list_matches_year_filter(client):
    resp = await client.get("/matches?year=2024")
    assert resp.status_code == 200
    for match in resp.json()["matches"]:
        assert match["tournament_year"] == "2024"

async def test_list_matches_invalid_year(client):
    resp = await client.get("/matches?year=24")
    assert resp.status_code == 422

async def test_list_matches_head_to_head(client):
    resp = await client.get("/matches?team=India&team2=Pakistan")
    assert resp.status_code == 200
    data = resp.json()
    for match in data["matches"]:
        teams = {match["team1"], match["team2"]}
        assert "India" in teams and "Pakistan" in teams

async def test_list_matches_filters_in_response(client):
    resp = await client.get("/matches?team=India&year=2024")
    assert resp.status_code == 200
    filters = resp.json()["filters"]
    assert filters["team"] == "India"
    assert filters["year"] == "2024"

async def test_list_matches_innings_scores_present(client):
    resp = await client.get("/matches?year=2024")
    assert resp.status_code == 200
    matches = resp.json()["matches"]
    if matches:
        # At least some matches should have innings scores
        scored = [m for m in matches if m.get("innings_scores")]
        assert len(scored) > 0

async def test_scorecard_invalid_match(client):
    resp = await client.get("/matches/999999/scorecard")
    assert resp.status_code == 404

async def test_scorecard_valid_match(client):
    # Get a real match id first
    matches = (await client.get("/matches?year=2024")).json()["matches"]
    if matches:
        mid = matches[0]["id"]
        resp = await client.get(f"/matches/{mid}/scorecard")
        assert resp.status_code == 200
        data = resp.json()
        assert "innings" in data
        assert "match" in data

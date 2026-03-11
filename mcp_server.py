"""
T20 DataHub MCP Server
Wraps the T20 World Cup API (t20-datahub-api.onrender.com) as an MCP server,
exposing match data, scorecards, fan profiles, and fantasy team management.
"""

import json
from typing import Optional
import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

BASE_URL = "https://t20-datahub-api.onrender.com"
TIMEOUT = 30.0
_auth_token: Optional[str] = None
mcp = FastMCP("t20_datahub_mcp")

def _get_headers() -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if _auth_token:
        headers["Authorization"] = f"Bearer {_auth_token}"
    return headers

async def _api_get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}{path}", headers=_get_headers(), params=params)
        resp.raise_for_status()
        return resp.json()

async def _api_post(path: str, body: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}{path}", headers=_get_headers(), json=body or {})
        resp.raise_for_status()
        return resp.json()

async def _api_put(path: str, body: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.put(f"{BASE_URL}{path}", headers=_get_headers(), json=body or {})
        resp.raise_for_status()
        return resp.json()

async def _api_delete(path: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.delete(f"{BASE_URL}{path}", headers=_get_headers())
        resp.raise_for_status()
        return resp.json() if resp.content else {"message": "Deleted successfully"}

def _fmt(data) -> str:
    return json.dumps(data, indent=2)

class LoginInput(BaseModel):
    username: str
    password: str

class MatchListInput(BaseModel):
    year: Optional[str] = None
    team: Optional[str] = None

class MatchIdInput(BaseModel):
    match_id: int

@mcp.tool(name="t20_login")
async def t20_login(params: LoginInput) -> str:
    """Login to T20 DataHub and store auth token."""
    global _auth_token
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/auth/login", data={"username": params.username, "password": params.password})
        resp.raise_for_status()
        data = resp.json()
    if "access_token" in data:
        _auth_token = data["access_token"]
        return _fmt({"message": "Login successful", **data})
    return _fmt(data)

@mcp.tool(name="t20_list_matches")
async def t20_list_matches(params: MatchListInput) -> str:
    """List T20 World Cup matches, optionally filtered by year or team."""
    query = {}
    if params.year: query["year"] = params.year
    if params.team: query["team"] = params.team
    data = await _api_get("/matches", params=query)
    return _fmt(data)

@mcp.tool(name="t20_get_scorecard")
async def t20_get_scorecard(params: MatchIdInput) -> str:
    """Get full batting and bowling scorecard for a match."""
    data = await _api_get(f"/matches/{params.match_id}/scorecard")
    return _fmt(data)

@mcp.tool(name="t20_get_teams")
async def t20_get_teams() -> str:
    """Get all T20 World Cup teams with win/loss statistics."""
    data = await _api_get("/options/teams")
    return _fmt(data)

@mcp.tool(name="t20_get_players")
async def t20_get_players() -> str:
    """Get all players across T20 World Cup teams."""
    data = await _api_get("/options/players")
    return _fmt(data)

@mcp.tool(name="t20_get_global_leaderboard")
async def t20_get_global_leaderboard() -> str:
    """Get the global fantasy cricket leaderboard."""
    data = await _api_get("/fantasy/leaderboard")
    return _fmt(data)

if __name__ == "__main__":
    mcp.run()

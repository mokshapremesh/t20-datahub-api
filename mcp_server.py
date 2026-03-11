import httpx
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

BASE_URL = "https://t20-datahub-api.onrender.com"

server = Server("t20-datahub")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_matches",
            description="Get T20 World Cup matches, optionally filtered by team or year",
            inputSchema={
                "type": "object",
                "properties": {
                    "team": {"type": "string", "description": "Team name e.g. India"},
                    "year": {"type": "string", "description": "Tournament year e.g. 2024"}
                }
            }
        ),
        Tool(
            name="get_scorecard",
            description="Get detailed scorecard for a specific match by match ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "match_id": {"type": "integer", "description": "Match ID"}
                },
                "required": ["match_id"]
            }
        ),
        Tool(
            name="get_teams",
            description="Get all T20 World Cup teams with win/loss stats",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {"type": "string", "description": "Filter by year"}
                }
            }
        ),
        Tool(
            name="get_fantasy_leaderboard",
            description="Get the global fantasy cricket leaderboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {"type": "string", "description": "Filter by year"}
                }
            }
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        if name == "get_matches":
            params = {}
            if "team" in arguments: params["team"] = arguments["team"]
            if "year" in arguments: params["year"] = arguments["year"]
            r = await client.get(f"{BASE_URL}/matches", params=params)
            return [TextContent(type="text", text=r.text)]
        elif name == "get_scorecard":
            r = await client.get(f"{BASE_URL}/matches/{arguments['match_id']}/scorecard")
            return [TextContent(type="text", text=r.text)]
        elif name == "get_teams":
            params = {}
            if "year" in arguments: params["year"] = arguments["year"]
            r = await client.get(f"{BASE_URL}/options/teams", params=params)
            return [TextContent(type="text", text=r.text)]
        elif name == "get_fantasy_leaderboard":
            params = {}
            if "year" in arguments: params["year"] = arguments["year"]
            r = await client.get(f"{BASE_URL}/fantasy/leaderboard", params=params)
            return [TextContent(type="text", text=r.text)]
        return [TextContent(type="text", text="Unknown tool")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())

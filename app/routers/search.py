from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import anthropic
import os

from app.db.session import get_session
from app.models.match import Match

router = APIRouter(prefix="/search", tags=["AI Search"])

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    query: str
    answer: str

@router.post("", response_model=SearchResponse)
async def ai_search(body: SearchRequest, session: AsyncSession = Depends(get_session)):
    """Natural language search powered by Claude AI. Ask anything about T20 World Cup data."""
    
    result = await session.execute(select(Match))
    matches = result.scalars().all()

    total = len(matches)
    years = sorted(set(m.tournament_year for m in matches if m.tournament_year))
    
    win_counts = {}
    for m in matches:
        if m.winner:
            win_counts[m.winner] = win_counts.get(m.winner, 0) + 1
    top_teams = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    recent = sorted(matches, key=lambda m: m.match_date or "", reverse=True)[:10]
    recent_summary = [
        f"{m.team1} vs {m.team2} ({m.tournament_year}) - Winner: {m.winner or 'TBD'}"
        for m in recent
    ]

    context = f"""You are an expert T20 cricket analyst with access to the T20 DataHub database.

DATABASE SUMMARY:
- Total matches: {total}
- Tournament years: {', '.join(str(y) for y in years)}
- Top teams by wins: {', '.join(f"{t}({w})" for t,w in top_teams)}
- Recent matches: {chr(10).join(recent_summary)}

Answer the user's question using this data. Be concise and specific."""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": f"{context}\n\nQuestion: {body.query}"}]
    )

    return SearchResponse(query=body.query, answer=message.content[0].text)

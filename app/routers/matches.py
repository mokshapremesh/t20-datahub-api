from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.db.session import get_session
from app.models.match import Match
from app.models.delivery import Delivery
from app.models.user import User
from app.services.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/matches", tags=["Matches"])


@router.get("")
async def list_matches(
    team: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    venue: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_session),
):
    query = select(Match)
    if team:
        query = query.where((Match.team1.ilike(f"%{team}%")) | (Match.team2.ilike(f"%{team}%")))
    if year:
        query = query.where(Match.tournament_year == year)
    if stage:
        query = query.where(Match.stage.ilike(f"%{stage}%"))
    if venue:
        query = query.where(Match.venue.ilike(f"%{venue}%"))
    query = query.order_by(Match.match_date.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    matches = result.scalars().all()
    return {"total": len(matches), "matches": [m.__dict__ for m in matches]}


@router.get("/{match_id}")
async def get_match(match_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match.__dict__


@router.get("/{match_id}/scorecard")
async def get_scorecard(match_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    deliveries = await session.execute(
        select(Delivery)
        .where(Delivery.match_id == match_id)
        .order_by(Delivery.innings_number, Delivery.ball_in_innings)
    )
    all_deliveries = deliveries.scalars().all()

    innings = {}
    for d in all_deliveries:
        key = d.innings_number
        if key not in innings:
            innings[key] = {
                "innings_number": key,
                "batting_team": d.batting_team,
                "bowling_team": d.bowling_team,
                "deliveries": [],
                "total_runs": 0,
                "total_wickets": 0,
            }
        innings[key]["deliveries"].append(d.__dict__)
        innings[key]["total_runs"] += d.runs_total
        if d.is_wicket:
            innings[key]["total_wickets"] += 1

    return {
        "match_id": match_id,
        "team1": match.team1,
        "team2": match.team2,
        "date": match.match_date,
        "venue": match.venue,
        "winner": match.winner,
        "innings": list(innings.values()),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_match(
    body: dict,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    match = Match(**body)
    session.add(match)
    await session.commit()
    await session.refresh(match)
    return match.__dict__


@router.put("/{match_id}")
async def update_match(
    match_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    result = await session.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    for key, value in body.items():
        if hasattr(match, key):
            setattr(match, key, value)
    await session.commit()
    await session.refresh(match)
    return match.__dict__


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    result = await session.execute(select(Match).where(Match.id == match_id))
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    await session.delete(match)
    await session.commit()

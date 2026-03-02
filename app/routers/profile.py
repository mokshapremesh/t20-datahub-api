from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.db.session import get_session
from app.models.fan_profile import FanProfile
from app.models.match import Match
from app.models.delivery import Delivery
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(prefix="/me", tags=["Fan Profile & Dashboard"])

class ProfileCreate(BaseModel):
    display_name:   Optional[str] = None
    fav_team:       Optional[str] = None
    fav_player_key: Optional[str] = None
    fav_year:       Optional[str] = None

class ProfileUpdate(BaseModel):
    display_name:   Optional[str] = None
    fav_team:       Optional[str] = None
    fav_player_key: Optional[str] = None
    fav_year:       Optional[str] = None

async def validate_team(team, session):
    exists = (await session.execute(select(Match.team1).where((Match.team1 == team) | (Match.team2 == team)).limit(1))).scalar()
    if not exists:
        raise HTTPException(status_code=400, detail=f"'{team}' not found. Use GET /options/teams")

async def validate_player(player_key, session):
    name = player_key.replace("_", " ")
    found = (await session.execute(select(Delivery.batter).where(Delivery.batter.ilike(f"%{name}%")).limit(1))).scalar()
    if not found:
        found = (await session.execute(select(Delivery.bowler).where(Delivery.bowler.ilike(f"%{name}%")).limit(1))).scalar()
    if not found:
        raise HTTPException(status_code=400, detail=f"'{player_key}' not found. Use GET /options/players")

@router.post("/profile", status_code=201)
async def create_profile(body: ProfileCreate, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Create your Fan Profile — sets favourite team, player, year"""
    existing = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Profile exists. Use PUT /me/profile to update.")
    if body.fav_team: await validate_team(body.fav_team, session)
    if body.fav_player_key: await validate_player(body.fav_player_key, session)
    profile = FanProfile(user_id=current_user.id, display_name=body.display_name, fav_team=body.fav_team, fav_player_key=body.fav_player_key, fav_year=body.fav_year)
    session.add(profile); await session.commit(); await session.refresh(profile)
    return {"message": "Profile created", "profile": {"display_name": profile.display_name, "fav_team": profile.fav_team, "fav_player_key": profile.fav_player_key, "fav_year": profile.fav_year, "created_at": str(profile.created_at)}, "links": {"self": "/me/profile", "dashboard": "/me/dashboard"}}

@router.get("/profile")
async def get_profile(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Get your stored profile preferences"""
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        return {"message": "No profile yet.", "links": {"create": "/me/profile", "teams": "/options/teams", "players": "/options/players"}}
    return {"user_id": current_user.id, "display_name": profile.display_name, "fav_team": profile.fav_team, "fav_player_key": profile.fav_player_key, "fav_year": profile.fav_year, "created_at": str(profile.created_at), "updated_at": str(profile.updated_at), "links": {"self": "/me/profile", "dashboard": "/me/dashboard"}}

@router.put("/profile")
async def update_profile(body: ProfileUpdate, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Update your preferences — all fields optional"""
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Use POST /me/profile first.")
    if body.fav_team is not None: await validate_team(body.fav_team, session); profile.fav_team = body.fav_team
    if body.fav_player_key is not None: await validate_player(body.fav_player_key, session); profile.fav_player_key = body.fav_player_key
    if body.display_name is not None: profile.display_name = body.display_name
    if body.fav_year is not None: profile.fav_year = body.fav_year
    await session.commit()
    return {"message": "Profile updated", "fav_team": profile.fav_team, "fav_player_key": profile.fav_player_key, "fav_year": profile.fav_year, "links": {"self": "/me/profile", "dashboard": "/me/dashboard"}}

@router.delete("/profile")
async def delete_profile(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Delete your profile"""
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found")
    await session.delete(profile); await session.commit()
    return {"message": "Profile deleted. Use POST /me/profile to start fresh."}

@router.get("/dashboard")
async def get_dashboard(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Personalised dashboard — computed live from ball-by-ball data"""
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Use POST /me/profile first.")

    result = {"profile": {"display_name": profile.display_name, "fav_team": profile.fav_team, "fav_player_key": profile.fav_player_key, "fav_year": profile.fav_year}, "dashboard": {}, "generated_at": datetime.utcnow().isoformat(), "links": {"profile": "/me/profile"}}

    if profile.fav_team:
        q = select(Match).where((Match.team1 == profile.fav_team) | (Match.team2 == profile.fav_team))
        if profile.fav_year: q = q.where(Match.tournament_year == profile.fav_year)
        matches = (await session.execute(q)).scalars().all()
        wins = sum(1 for m in matches if m.winner == profile.fav_team)
        stage_dist = {}
        for m in matches:
            s = m.stage or "Group Stage"; stage_dist[s] = stage_dist.get(s, 0) + 1
        year_record = {}
        for m in matches:
            y = m.tournament_year
            if y not in year_record: year_record[y] = {"matches": 0, "wins": 0}
            year_record[y]["matches"] += 1
            if m.winner == profile.fav_team: year_record[y]["wins"] += 1
        match_ids = [m.id for m in matches]
        n = max(len(matches), 1)
        bat = (await session.execute(select(func.sum(Delivery.runs_total).label("runs")).where(Delivery.match_id.in_(match_ids), Delivery.batting_team == profile.fav_team))).first()
        bowl = (await session.execute(select(func.sum(Delivery.runs_total).label("runs")).where(Delivery.match_id.in_(match_ids), Delivery.bowling_team == profile.fav_team))).first()
        death = (await session.execute(select(func.sum(Delivery.runs_total).label("runs"), func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls")).where(Delivery.match_id.in_(match_ids), Delivery.bowling_team == profile.fav_team, Delivery.over >= 16))).first()
        result["dashboard"]["team"] = {"team": profile.fav_team, "summary": {"matches": len(matches), "wins": wins, "losses": len(matches)-wins, "win_rate": round(wins/n*100, 1)}, "stage_distribution": stage_dist, "year_by_year": {y: {"matches": v["matches"], "wins": v["wins"], "losses": v["matches"]-v["wins"]} for y, v in sorted(year_record.items())}, "batting": {"avg_runs_scored_per_match": round((bat.runs or 0)/n, 1)}, "bowling": {"avg_runs_conceded_per_match": round((bowl.runs or 0)/n, 1), "death_overs_economy": round((death.runs or 0)/max(death.balls or 1, 1)*6, 2)}}

    if profile.fav_player_key:
        name = profile.fav_player_key.replace("_", " ")
        resolved = (await session.execute(select(Delivery.batter).where(Delivery.batter.ilike(f"%{name}%")).limit(1))).scalar()
        if not resolved: resolved = (await session.execute(select(Delivery.bowler).where(Delivery.bowler.ilike(f"%{name}%")).limit(1))).scalar()
        if resolved:
            mids = None
            if profile.fav_year: mids = (await session.execute(select(Match.id).where(Match.tournament_year == profile.fav_year))).scalars().all()
            bat_q = select(func.sum(Delivery.runs_batter).label("runs"), func.count(Delivery.id).filter(Delivery.is_legal==True).label("balls"), func.count(Delivery.id).filter(Delivery.runs_batter==4).label("fours"), func.count(Delivery.id).filter(Delivery.runs_batter==6).label("sixes")).where(Delivery.batter == resolved)
            if mids is not None: bat_q = bat_q.where(Delivery.match_id.in_(mids))
            bat = (await session.execute(bat_q)).first()
            bowl_q = select(func.count(Delivery.id).filter(Delivery.is_wicket==True).label("wickets"), func.sum(Delivery.runs_total).label("runs_conceded"), func.count(Delivery.id).filter(Delivery.is_legal==True).label("balls")).where(Delivery.bowler == resolved)
            if mids is not None: bowl_q = bowl_q.where(Delivery.match_id.in_(mids))
            bowl = (await session.execute(bowl_q)).first()
            runs = bat.runs or 0; balls = bat.balls or 1
            best_bat = (await session.execute(select(Delivery.match_id, func.sum(Delivery.runs_batter).label("runs")).where(Delivery.batter == resolved).group_by(Delivery.match_id).order_by(func.sum(Delivery.runs_batter).desc()).limit(1))).first()
            best_match = None
            if best_bat:
                m = await session.get(Match, best_bat.match_id)
                if m: best_match = {"match": f"{m.team1} vs {m.team2} ({m.match_date})", "runs": best_bat.runs}
            yr_q = select(Match.tournament_year, func.sum(Delivery.runs_batter).label("runs"), func.count(Delivery.id).filter(Delivery.is_wicket==True).label("wickets"), func.count(distinct(Delivery.match_id)).label("matches")).join(Match, Delivery.match_id==Match.id).where((Delivery.batter==resolved)|(Delivery.bowler==resolved)).group_by(Match.tournament_year).order_by(Match.tournament_year)
            yr_rows = (await session.execute(yr_q)).all()
            result["dashboard"]["player"] = {"player": resolved, "batting": {"runs": runs, "balls": bat.balls or 0, "strike_rate": round(runs/balls*100, 1), "fours": bat.fours or 0, "sixes": bat.sixes or 0}, "bowling": {"wickets": bowl.wickets or 0, "economy": round((bowl.runs_conceded or 0)/max(bowl.balls or 1, 1)*6, 2)}, "best_match": best_match, "year_by_year": {r.tournament_year: {"matches": r.matches, "runs": r.runs or 0, "wickets": r.wickets or 0} for r in yr_rows}}

    return result

options_router = APIRouter(prefix="/options", tags=["Options & Dropdowns"])

@options_router.get("/teams")
async def get_teams(session: AsyncSession = Depends(get_session)):
    """All teams with match counts — use for fav_team dropdown"""
    matches = (await session.execute(select(Match))).scalars().all()
    team_stats = {}
    for m in matches:
        for team in [m.team1, m.team2]:
            if team not in team_stats: team_stats[team] = {"matches": 0, "wins": 0}
            team_stats[team]["matches"] += 1
            if m.winner == team: team_stats[team]["wins"] += 1
    teams = sorted([{"team_key": t, "display_name": t, "matches": s["matches"], "wins": s["wins"], "win_rate": round(s["wins"]/s["matches"]*100, 1)} for t, s in team_stats.items()], key=lambda x: x["matches"], reverse=True)
    return {"total": len(teams), "teams": teams}

@options_router.get("/players")
async def get_players(team: Optional[str] = Query(None), year: Optional[str] = Query(None), session: AsyncSession = Depends(get_session)):
    """Players with stats — use for fav_player_key dropdown"""
    match_q = select(Match.id)
    if year: match_q = match_q.where(Match.tournament_year == year)
    if team: match_q = match_q.where((Match.team1 == team) | (Match.team2 == team))
    match_ids = (await session.execute(match_q)).scalars().all()
    if not match_ids: raise HTTPException(status_code=404, detail="No matches found")
    batters = (await session.execute(select(Delivery.batter, Delivery.batting_team, func.sum(Delivery.runs_batter).label("runs"), func.count(Delivery.id).filter(Delivery.is_legal==True).label("balls"), func.count(Delivery.id).filter(Delivery.runs_batter==4).label("fours"), func.count(Delivery.id).filter(Delivery.runs_batter==6).label("sixes")).where(Delivery.match_id.in_(match_ids)).group_by(Delivery.batter, Delivery.batting_team))).all()
    bowlers = (await session.execute(select(Delivery.bowler, func.count(Delivery.id).filter(Delivery.is_wicket==True).label("wickets"), func.sum(Delivery.runs_total).label("runs_conceded"), func.count(Delivery.id).filter(Delivery.is_legal==True).label("balls")).where(Delivery.match_id.in_(match_ids)).group_by(Delivery.bowler))).all()
    player_map = {}
    for b in batters:
        runs = b.runs or 0; balls = b.balls or 1
        player_map[b.batter] = {"player_key": b.batter, "team": b.batting_team, "runs": runs, "strike_rate": round(runs/balls*100, 1), "fours": b.fours or 0, "sixes": b.sixes or 0, "wickets": 0, "economy": 0}
    for b in bowlers:
        balls = b.balls or 1; economy = round((b.runs_conceded or 0)/balls*6, 2)
        if b.bowler in player_map: player_map[b.bowler]["wickets"] = b.wickets or 0; player_map[b.bowler]["economy"] = economy
        else: player_map[b.bowler] = {"player_key": b.bowler, "team": None, "runs": 0, "strike_rate": 0, "fours": 0, "sixes": 0, "wickets": b.wickets or 0, "economy": economy}
    players = sorted(player_map.values(), key=lambda x: x["runs"] + x["wickets"]*25, reverse=True)
    return {"total": len(players), "filters": {"team": team, "year": year}, "players": players}

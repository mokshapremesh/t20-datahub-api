from fastapi import APIRouter, Depends, HTTPException, status, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.db.session import get_session
from app.models.fantasy import FantasyTeam, FantasyTeamPlayer, FantasyEntry
from app.models.match import Match
from app.models.delivery import Delivery
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(prefix="/fantasy", tags=["Fantasy Season Challenge"])

def make_match_key(match):
    t1 = match.team1[:3].upper()
    t2 = match.team2[:3].upper()
    date = str(match.match_date)
    stage_map = {"Final": "F", "Semi Final": "SF", "Super 8": "S8", "Super 12": "S12", "Group": "GS"}
    stage = "GS"
    if match.stage:
        for k, v in stage_map.items():
            if k.lower() in match.stage.lower():
                stage = v
                break
    return f"{t1}-{t2}-{date}-{stage}"

def make_player_key(name):
    return name.strip().replace(" ", "_").upper()

async def resolve_match_key(match_key, session):
    parts = match_key.split("-")
    if len(parts) < 5:
        raise HTTPException(status_code=400, detail="Invalid match_key. Example: IND-ENG-2024-06-27-SF")
    t1_prefix = parts[0].upper()
    t2_prefix = parts[1].upper()
    date_str = f"{parts[2]}-{parts[3]}-{parts[4]}"
    matches = (await session.execute(select(Match))).scalars().all()
    for m in matches:
        t1 = m.team1[:3].upper()
        t2 = m.team2[:3].upper()
        if (t1 == t1_prefix or t2 == t1_prefix) and (t1 == t2_prefix or t2 == t2_prefix):
            if str(m.match_date) == date_str:
                return m
    raise HTTPException(status_code=404, detail=f"Match '{match_key}' not found. Use GET /fantasy/match to browse.")

async def resolve_player_key(player_key, match_id, session):
    target = player_key.replace("_", " ").upper()
    batters = (await session.execute(select(Delivery.batter).where(Delivery.match_id == match_id).distinct())).scalars().all()
    bowlers = (await session.execute(select(Delivery.bowler).where(Delivery.match_id == match_id).distinct())).scalars().all()
    all_players = list(set(list(batters) + list(bowlers)))
    for p in all_players:
        if p.replace(" ", "_").upper() == target:
            return p
    key_last = player_key.split("_")[-1].upper()
    for p in all_players:
        if p.split()[-1].upper() == key_last:
            return p
    raise HTTPException(status_code=400, detail=f"'{player_key}' not found. Use GET /fantasy/match/{{match_key}}/players")

async def score_player(player_name, match_id, role, session):
    bat = (await session.execute(select(
        func.sum(Delivery.runs_batter).label("runs"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
        func.count(Delivery.id).filter(Delivery.is_wicket == True).label("dismissed"),
    ).where(Delivery.match_id == match_id, Delivery.batter == player_name))).first()

    runs = bat.runs or 0; fours = bat.fours or 0; sixes = bat.sixes or 0
    balls_faced = bat.balls or 0; dismissed = (bat.dismissed or 0) > 0
    bat_pts = runs + fours + (sixes * 2)
    bat_bonuses = []
    if runs >= 50: bat_pts += 20; bat_bonuses.append("50+ (+20)")
    elif runs >= 30: bat_pts += 10; bat_bonuses.append("30+ (+10)")
    if runs == 0 and dismissed: bat_pts -= 5; bat_bonuses.append("duck (-5)")

    bowl = (await session.execute(select(
        func.count(Delivery.id).filter(Delivery.is_wicket == True, Delivery.wicket_type.isnot(None), ~func.lower(Delivery.wicket_type).in_({"run out", "retired hurt", "retired out", "obstructing the field", "hit the ball twice", "handled the ball", "timed out"})).label("wickets"),
        func.sum(Delivery.runs_total).label("runs_conceded"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls_bowled"),
    ).where(Delivery.match_id == match_id, Delivery.bowler == player_name))).first()

    wickets = bowl.wickets or 0; runs_conceded = bowl.runs_conceded or 0; balls_bowled = bowl.balls_bowled or 0
    economy = round((runs_conceded / balls_bowled) * 6, 2) if balls_bowled > 0 else 0.0
    bowl_pts = wickets * 25; bowl_bonuses = []
    if wickets >= 4: bowl_pts += 20; bowl_bonuses.append("4W+ (+20)")
    elif wickets >= 3: bowl_pts += 10; bowl_bonuses.append("3W (+10)")
    if balls_bowled >= 6:
        if economy < 6: bowl_pts += 6; bowl_bonuses.append("eco<6 (+6)")
        elif economy < 7: bowl_pts += 4; bowl_bonuses.append("eco<7 (+4)")
        elif economy < 8: bowl_pts += 2; bowl_bonuses.append("eco<8 (+2)")
        elif economy >= 10: bowl_pts -= 4; bowl_bonuses.append("eco>10 (-4)")
        elif economy >= 9: bowl_pts -= 2; bowl_bonuses.append("eco>9 (-2)")

    base_points = bat_pts + bowl_pts
    multiplier = 2.0 if role == "CAPTAIN" else 1.5 if role == "VICE_CAPTAIN" else 1.0
    final_points = round(base_points * multiplier, 1)
    return {
        "player": player_name, "player_key": make_player_key(player_name), "role": role,
        "batting": {"runs": runs, "balls_faced": balls_faced, "fours": fours, "sixes": sixes, "dismissed": dismissed, "bonuses": bat_bonuses, "points": bat_pts},
        "bowling": {"wickets": wickets, "balls_bowled": balls_bowled, "economy": economy, "bonuses": bowl_bonuses, "points": bowl_pts},
        "base_points": base_points, "multiplier": multiplier, "final_points": final_points,
        "explain": f"Bat:{runs}r+{fours}x4+{sixes}x6={bat_pts}pts | Bowl:{wickets}w@{economy}={bowl_pts}pts | {base_points}x{multiplier}={final_points}pts",
    }

@router.get("/match", include_in_schema=False)
async def find_match(
    team1: Optional[str] = Query(None), team2: Optional[str] = Query(None),
    year: Optional[str] = Query(None), stage: Optional[str] = Query(None),
    date: Optional[str] = Query(None), session: AsyncSession = Depends(get_session),
):
    """STEP 1 — Find a match. Returns match_key slug. Example: ?team1=India&year=2024&stage=Semi Final"""
    query = select(Match)
    if team1 and team2:
        query = query.where(((Match.team1 == team1) & (Match.team2 == team2)) | ((Match.team1 == team2) & (Match.team2 == team1)))
    elif team1:
        query = query.where((Match.team1 == team1) | (Match.team2 == team1))
    elif team2:
        query = query.where((Match.team1 == team2) | (Match.team2 == team2))
    if year: query = query.where(Match.tournament_year == year)
    if stage: query = query.where(Match.stage.ilike(f"%{stage}%"))
    if date: query = query.where(Match.match_date == date)
    matches = (await session.execute(query.order_by(Match.match_date.desc()).limit(20))).scalars().all()
    if not matches:
        raise HTTPException(status_code=404, detail="No matches found. Available years: 2014, 2016, 2021, 2022, 2024, 2026")
    return {
        "total": len(matches),
        "next_step": "Copy a match_key → GET /fantasy/match/{match_key}/players",
        "matches": [{"match_key": make_match_key(m), "matchup": f"{m.team1} vs {m.team2}", "year": m.tournament_year, "date": str(m.match_date), "venue": m.venue, "stage": m.stage or "Group Stage"} for m in matches],
    }

@router.get("/match/{match_key}/players", include_in_schema=False)
async def get_match_players(match_key: str, session: AsyncSession = Depends(get_session)):
    """STEP 2 — See all players + estimated points. Copy player_key to build XI."""
    match = await resolve_match_key(match_key, session)
    batters_q = (await session.execute(select(Delivery.batter, Delivery.batting_team, func.sum(Delivery.runs_batter).label("runs"), func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"), func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"), func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes"), func.count(Delivery.id).filter(Delivery.is_wicket == True).label("dismissed")).where(Delivery.match_id == match.id).group_by(Delivery.batter, Delivery.batting_team))).all()
    bowlers_q = (await session.execute(select(Delivery.bowler, Delivery.bowling_team, func.count(Delivery.id).filter(Delivery.is_wicket == True, Delivery.wicket_type.isnot(None), ~func.lower(Delivery.wicket_type).in_({"run out", "retired hurt", "retired out", "obstructing the field", "hit the ball twice", "handled the ball", "timed out"})).label("wickets"), func.sum(Delivery.runs_total).label("runs_conceded"), func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls")).where(Delivery.match_id == match.id).group_by(Delivery.bowler, Delivery.bowling_team))).all()
    player_map = {}
    for b in batters_q:
        runs = b.runs or 0; balls = b.balls or 1; fours = b.fours or 0; sixes = b.sixes or 0
        dismissed = (b.dismissed or 0) > 0
        bat_pts = runs + fours + (sixes * 2)
        if runs >= 50: bat_pts += 20
        elif runs >= 30: bat_pts += 10
        if runs == 0 and dismissed: bat_pts -= 5
        player_map[b.batter] = {"player_key": make_player_key(b.batter), "team": b.batting_team, "runs": runs, "balls": b.balls or 0, "fours": fours, "sixes": sixes, "wickets": 0, "economy": 0, "estimated_points": bat_pts}
    for b in bowlers_q:
        balls = b.balls or 1; runs = b.runs_conceded or 0; economy = round(runs / balls * 6, 2); wickets = b.wickets or 0
        bowl_pts = wickets * 25
        if wickets >= 4: bowl_pts += 20
        elif wickets >= 3: bowl_pts += 10
        if balls >= 6:
            if economy < 6: bowl_pts += 6
            elif economy < 7: bowl_pts += 4
            elif economy < 8: bowl_pts += 2
            elif economy >= 10: bowl_pts -= 4
            elif economy >= 9: bowl_pts -= 2
        if b.bowler in player_map:
            player_map[b.bowler]["wickets"] = wickets; player_map[b.bowler]["economy"] = economy; player_map[b.bowler]["estimated_points"] += bowl_pts
        else:
            player_map[b.bowler] = {"player_key": make_player_key(b.bowler), "team": b.bowling_team, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "wickets": wickets, "economy": economy, "estimated_points": bowl_pts}
    players = sorted(player_map.values(), key=lambda x: x["estimated_points"], reverse=True)
    t1 = [p for p in players if p["team"] == match.team1]
    t2 = [p for p in players if p["team"] == match.team2]
    return {
        "match_key": match_key, "matchup": f"{match.team1} vs {match.team2}", "date": str(match.match_date), "year": match.tournament_year,
        "tip": "Set 1 CAPTAIN (x2pts) and 1 VICE_CAPTAIN (x1.5pts)",
        "players": {
            match.team1: [{"rank": i+1, "player_key": p["player_key"], "runs": p["runs"], "wickets": p["wickets"], "estimated_pts": round(p["estimated_points"], 1)} for i, p in enumerate(t1)],
            match.team2: [{"rank": i+1, "player_key": p["player_key"], "runs": p["runs"], "wickets": p["wickets"], "estimated_pts": round(p["estimated_points"], 1)} for i, p in enumerate(t2)],
        },
    }

@router.post("/teams", include_in_schema=False, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_name: str = Form(..., description="e.g. My Dream XI"),
    match_key: str = Form(..., description="e.g. IND-ENG-2024-06-27-SF"),
    session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user),
):
    """STEP 3 — Create your XI shell. Add players next."""
    match = await resolve_match_key(match_key, session)
    team = FantasyTeam(user_id=current_user.id, team_name=team_name, match_id=match.id)
    session.add(team); await session.commit(); await session.refresh(team)
    return {"team_id": team.id, "team_name": team.team_name, "match_key": match_key, "match": f"{match.team1} vs {match.team2} ({match.tournament_year})", "players_added": 0, "next_steps": [f"POST /fantasy/teams/{team.id}/players?player_key=V_KOHLI  (x11)", f"PUT  /fantasy/teams/{team.id}/captain?player_key=V_KOHLI", f"PUT  /fantasy/teams/{team.id}/vice-captain?player_key=JJ_BUMRAH", f"GET  /fantasy/teams/{team.id}  <- verify"]}

@router.post("/teams/{team_id}/players", include_in_schema=False, status_code=status.HTTP_201_CREATED)
async def add_player(
    team_id: int, player_key: str = Query(..., description="e.g. V_KOHLI"),
    session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user),
):
    """Add a player to your XI. Repeat x11."""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    count = (await session.execute(select(func.count(FantasyTeamPlayer.id)).where(FantasyTeamPlayer.fantasy_team_id == team_id))).scalar() or 0
    if count >= 11: raise HTTPException(status_code=400, detail="Already 11 players. Remove one first.")
    player_name = await resolve_player_key(player_key, team.match_id, session)
    existing = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id, FantasyTeamPlayer.player_name == player_name))).scalar_one_or_none()
    if existing: raise HTTPException(status_code=400, detail=f"{player_name} already in team")
    match = await session.get(Match, team.match_id)
    session.add(FantasyTeamPlayer(fantasy_team_id=team_id, player_name=player_name, tournament_year=match.tournament_year, role="PLAYER", order=count))
    await session.commit()
    new_count = count + 1
    return {"added": player_name, "player_key": player_key, "players_added": new_count, "players_remaining": 11 - new_count, "message": f"✅ {player_name} added. {11-new_count} more to go." if new_count < 11 else "✅ XI complete! Set captain and vice captain."}

@router.delete("/teams/{team_id}/players/{player_key:path}", include_in_schema=False)
async def remove_player(team_id: int, player_key: str, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Remove a player from your XI"""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    player_name = await resolve_player_key(player_key, team.match_id, session)
    player = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id, FantasyTeamPlayer.player_name == player_name))).scalar_one_or_none()
    if not player: raise HTTPException(status_code=404, detail=f"{player_name} not in team")
    await session.delete(player); await session.commit()
    count = (await session.execute(select(func.count(FantasyTeamPlayer.id)).where(FantasyTeamPlayer.fantasy_team_id == team_id))).scalar() or 0
    return {"message": f"✅ {player_name} removed", "players_in_team": count}

@router.put("/teams/{team_id}/captain", include_in_schema=False)
async def set_captain(team_id: int, player_key: str = Query(..., description="e.g. V_KOHLI"), session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Set captain — 2x points"""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    player_name = await resolve_player_key(player_key, team.match_id, session)
    existing_c = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id, FantasyTeamPlayer.role == "CAPTAIN"))).scalar_one_or_none()
    if existing_c: existing_c.role = "PLAYER"
    new_c = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id, FantasyTeamPlayer.player_name == player_name))).scalar_one_or_none()
    if not new_c: raise HTTPException(status_code=400, detail=f"{player_name} not in team")
    if new_c.role == "VICE_CAPTAIN": raise HTTPException(status_code=400, detail=f"{player_name} is already vice captain")
    new_c.role = "CAPTAIN"; await session.commit()
    return {"message": f"⭐ {player_name} is CAPTAIN (x2 points)"}

@router.put("/teams/{team_id}/vice-captain", include_in_schema=False)
async def set_vice_captain(team_id: int, player_key: str = Query(..., description="e.g. JJ_BUMRAH"), session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Set vice captain — 1.5x points"""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    player_name = await resolve_player_key(player_key, team.match_id, session)
    existing_vc = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id, FantasyTeamPlayer.role == "VICE_CAPTAIN"))).scalar_one_or_none()
    if existing_vc: existing_vc.role = "PLAYER"
    new_vc = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id, FantasyTeamPlayer.player_name == player_name))).scalar_one_or_none()
    if not new_vc: raise HTTPException(status_code=400, detail=f"{player_name} not in team")
    if new_vc.role == "CAPTAIN": raise HTTPException(status_code=400, detail=f"{player_name} is already captain")
    new_vc.role = "VICE_CAPTAIN"; await session.commit()
    return {"message": f"🔵 {player_name} is VICE CAPTAIN (x1.5 points)"}

@router.get("/teams", include_in_schema=False)
async def list_teams(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """List all your Fantasy XIs"""
    teams = (await session.execute(select(FantasyTeam).where(FantasyTeam.user_id == current_user.id).order_by(FantasyTeam.created_at.desc()))).scalars().all()
    result = []
    for t in teams:
        players = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == t.id).order_by(FantasyTeamPlayer.order))).scalars().all()
        match = await session.get(Match, t.match_id) if t.match_id else None
        captain = next((p.player_name for p in players if p.role == "CAPTAIN"), None)
        vc = next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None)
        result.append({"team_id": t.id, "team_name": t.team_name, "match_key": make_match_key(match) if match else None, "players_added": len(players), "complete": len(players) == 11, "captain": captain or "Not set", "vice_captain": vc or "Not set", "ready": len(players) == 11 and bool(captain) and bool(vc)})
    return {"total": len(result), "teams": result}

@router.get("/teams/{team_id}", include_in_schema=False)
async def get_team(team_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """View your XI — readiness check"""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    players = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id).order_by(FantasyTeamPlayer.order))).scalars().all()
    match = await session.get(Match, team.match_id) if team.match_id else None
    captain = next((p.player_name for p in players if p.role == "CAPTAIN"), None)
    vc = next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None)
    ready = len(players) == 11 and bool(captain) and bool(vc)
    warnings = []
    if len(players) < 11: warnings.append(f"Need {11-len(players)} more players")
    if not captain: warnings.append(f"Set captain -> PUT /fantasy/teams/{team_id}/captain?player_key=...")
    if not vc: warnings.append(f"Set vice captain -> PUT /fantasy/teams/{team_id}/vice-captain?player_key=...")
    return {"team_id": team.id, "team_name": team.team_name, "match_key": make_match_key(match) if match else None, "ready_to_submit": ready, "warnings": warnings, "captain": captain or "Not set", "vice_captain": vc or "Not set", "squad": [{"player_key": make_player_key(p.player_name), "player_name": p.player_name, "role": p.role} for p in players], "next_step": f"POST /fantasy/entries?fantasy_team_id={team_id}" if ready else "Complete XI first"}

@router.put("/teams/{team_id}", include_in_schema=False)
async def rename_team(team_id: int, team_name: str = Form(...), session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Rename your Fantasy XI"""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    old = team.team_name; team.team_name = team_name.strip(); await session.commit()
    return {"message": f"Renamed '{old}' to '{team.team_name}'", "team_id": team_id}

@router.delete("/teams/{team_id}", include_in_schema=False, status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Delete your Fantasy XI"""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    await session.delete(team); await session.commit()

@router.post("/entries", include_in_schema=False, status_code=status.HTTP_201_CREATED)
async def create_entry(fantasy_team_id: int = Query(...), session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """STEP 4 — Enter your XI into the match."""
    team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == fantasy_team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not team: raise HTTPException(status_code=404, detail="Fantasy team not found")
    match = await session.get(Match, team.match_id)
    players = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id))).scalars().all()
    if len(players) != 11: raise HTTPException(status_code=400, detail=f"Need 11 players — have {len(players)}")
    if not any(p.role == "CAPTAIN" for p in players): raise HTTPException(status_code=400, detail="No captain set")
    if not any(p.role == "VICE_CAPTAIN" for p in players): raise HTTPException(status_code=400, detail="No vice captain set")
    existing = (await session.execute(select(FantasyEntry).where(FantasyEntry.user_id == current_user.id, FantasyEntry.match_id == team.match_id))).scalar_one_or_none()
    if existing: raise HTTPException(status_code=400, detail=f"Already entered this match. Entry: {existing.id}")
    entry = FantasyEntry(user_id=current_user.id, match_id=team.match_id, fantasy_team_id=fantasy_team_id, status="DRAFT")
    session.add(entry); await session.commit(); await session.refresh(entry)
    captain = next((p.player_name for p in players if p.role == "CAPTAIN"), None)
    vc = next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None)
    return {"entry_id": entry.id, "status": "DRAFT", "match": f"{match.team1} vs {match.team2} ({match.match_date})", "match_key": make_match_key(match), "fantasy_team": team.team_name, "captain": captain, "vice_captain": vc, "next_steps": [f"POST /fantasy/entries/{entry.id}/submit", f"DELETE /fantasy/entries/{entry.id} to withdraw"]}

@router.post("/entries/{entry_id}/submit", include_in_schema=False)
async def submit_entry(entry_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Lock your entry. Then reveal to score."""
    entry = (await session.execute(select(FantasyEntry).where(FantasyEntry.id == entry_id, FantasyEntry.user_id == current_user.id))).scalar_one_or_none()
    if not entry: raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != "DRAFT": raise HTTPException(status_code=400, detail=f"Entry is already {entry.status}")
    entry.status = "SUBMITTED"; await session.commit()
    return {"entry_id": entry.id, "status": "SUBMITTED", "message": "Entry locked", "next_step": f"POST /fantasy/entries/{entry_id}/reveal"}

@router.get("/entries", include_in_schema=False)
async def list_entries(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Your full entry history"""
    entries = (await session.execute(select(FantasyEntry).where(FantasyEntry.user_id == current_user.id).order_by(FantasyEntry.created_at.desc()))).scalars().all()
    result = []
    for e in entries:
        match = await session.get(Match, e.match_id)
        team = await session.get(FantasyTeam, e.fantasy_team_id)
        result.append({"entry_id": e.id, "match_key": make_match_key(match) if match else None, "match": f"{match.team1} vs {match.team2} ({match.match_date})" if match else None, "fantasy_team": team.team_name if team else None, "status": e.status, "total_points": e.total_points, "rank_global": e.rank_global})
    revealed = [e for e in entries if e.status == "REVEALED"]
    return {"total_entries": len(entries), "revealed": len(revealed), "best_score": max((e.total_points for e in revealed if e.total_points), default=None), "entries": result}

@router.get("/entries/{entry_id}", include_in_schema=False)
async def get_entry(entry_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """View entry — breakdown shown if revealed"""
    entry = (await session.execute(select(FantasyEntry).where(FantasyEntry.id == entry_id, FantasyEntry.user_id == current_user.id))).scalar_one_or_none()
    if not entry: raise HTTPException(status_code=404, detail="Entry not found")
    match = await session.get(Match, entry.match_id)
    team = await session.get(FantasyTeam, entry.fantasy_team_id)
    response = {"entry_id": entry.id, "match_key": make_match_key(match) if match else None, "match": f"{match.team1} vs {match.team2} ({match.match_date})", "fantasy_team": team.team_name if team else None, "status": entry.status, "total_points": entry.total_points, "rank_global": entry.rank_global}
    if entry.status == "REVEALED" and entry.breakdown:
        response["actual_winner"] = match.winner; response["breakdown"] = entry.breakdown
    return response

@router.put("/entries/{entry_id}", include_in_schema=False)
async def update_entry(entry_id: int, fantasy_team_id: int = Query(...), session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Swap fantasy team — only while DRAFT"""
    entry = (await session.execute(select(FantasyEntry).where(FantasyEntry.id == entry_id, FantasyEntry.user_id == current_user.id))).scalar_one_or_none()
    if not entry: raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != "DRAFT": raise HTTPException(status_code=400, detail=f"Cannot edit — entry is {entry.status}")
    new_team = (await session.execute(select(FantasyTeam).where(FantasyTeam.id == fantasy_team_id, FantasyTeam.user_id == current_user.id))).scalar_one_or_none()
    if not new_team: raise HTTPException(status_code=404, detail="Fantasy team not found")
    entry.fantasy_team_id = fantasy_team_id; await session.commit()
    return {"message": f"Swapped to '{new_team.team_name}'", "entry_id": entry_id}

@router.delete("/entries/{entry_id}", include_in_schema=False, status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(entry_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Withdraw entry — only before reveal"""
    entry = (await session.execute(select(FantasyEntry).where(FantasyEntry.id == entry_id, FantasyEntry.user_id == current_user.id))).scalar_one_or_none()
    if not entry: raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == "REVEALED": raise HTTPException(status_code=400, detail="Cannot delete a revealed entry")
    await session.delete(entry); await session.commit()

@router.post("/entries/{entry_id}/reveal", include_in_schema=False)
async def reveal_entry(entry_id: int, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """FLAGSHIP — Score your XI from ball-by-ball data. Captain 2x. Vice 1.5x."""
    entry = (await session.execute(select(FantasyEntry).where(FantasyEntry.id == entry_id, FantasyEntry.user_id == current_user.id))).scalar_one_or_none()
    if not entry: raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == "REVEALED": raise HTTPException(status_code=400, detail="Already revealed")
    if entry.status == "DRAFT": raise HTTPException(status_code=400, detail=f"Submit first -> POST /fantasy/entries/{entry_id}/submit")
    match = await session.get(Match, entry.match_id)
    team = await session.get(FantasyTeam, entry.fantasy_team_id)
    players = (await session.execute(select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == entry.fantasy_team_id).order_by(FantasyTeamPlayer.order))).scalars().all()
    breakdown = []; total_points = 0.0
    for p in players:
        scored = await score_player(p.player_name, entry.match_id, p.role, session)
        breakdown.append(scored); total_points += scored["final_points"]
    total_points = round(total_points, 1)
    others = (await session.execute(select(FantasyEntry).where(FantasyEntry.match_id == entry.match_id, FantasyEntry.status == "REVEALED"))).scalars().all()
    rank = sum(1 for e in others if (e.total_points or 0) > total_points) + 1
    entry.status = "REVEALED"; entry.total_points = total_points; entry.rank_global = rank; entry.breakdown = breakdown
    await session.commit()
    pretty = []
    for b in breakdown:
        icon = "CAPTAIN" if b["role"] == "CAPTAIN" else "VICE" if b["role"] == "VICE_CAPTAIN" else ""
        pretty.append(f"{icon} {b['player']} -> {b['batting']['runs']}r {b['bowling']['wickets']}w -> {b['base_points']} x {b['multiplier']} = {b['final_points']}pts")
    pretty.append(f"TOTAL: {total_points} pts | Rank #{rank} of {len(others)+1}")
    return {"entry_id": entry.id, "match": f"{match.team1} vs {match.team2} ({match.match_date})", "match_key": make_match_key(match), "actual_winner": match.winner, "fantasy_team": team.team_name if team else None, "status": "REVEALED", "total_points": total_points, "rank_global": rank, "total_entries_this_match": len(others) + 1, "breakdown": breakdown, "pretty_summary": pretty}

@router.get("/leaderboard_old/{match_key}", include_in_schema=False)
async def match_leaderboard(match_key: str, limit: int = Query(10), session: AsyncSession = Depends(get_session)):
    """Leaderboard for a specific match"""
    match = await resolve_match_key(match_key, session)
    entries = (await session.execute(select(FantasyEntry).where(FantasyEntry.match_id == match.id, FantasyEntry.status == "REVEALED").order_by(FantasyEntry.total_points.desc()).limit(limit))).scalars().all()
    board = []
    for i, e in enumerate(entries):
        user = await session.get(User, e.user_id)
        team = await session.get(FantasyTeam, e.fantasy_team_id)
        board.append({"rank": i+1, "username": user.username if user else "Unknown", "fantasy_team": team.team_name if team else None, "total_points": e.total_points})
    return {"match_key": match_key, "match": f"{match.team1} vs {match.team2} ({match.match_date})", "actual_winner": match.winner, "total_entries": len(entries), "leaderboard": board}

@router.get("/leaderboard_old", include_in_schema=False)
async def global_leaderboard(year: Optional[str] = Query(None), limit: int = Query(10), session: AsyncSession = Depends(get_session)):
    """Global top scores across all matches"""
    entries = (await session.execute(select(FantasyEntry).where(FantasyEntry.status == "REVEALED").order_by(FantasyEntry.total_points.desc()))).scalars().all()
    board = []
    for e in entries:
        match = await session.get(Match, e.match_id)
        if year and match and match.tournament_year != year: continue
        user = await session.get(User, e.user_id)
        team = await session.get(FantasyTeam, e.fantasy_team_id)
        board.append({"username": user.username if user else "Unknown", "fantasy_team": team.team_name if team else None, "match_key": make_match_key(match) if match else None, "year": match.tournament_year if match else None, "total_points": e.total_points})
        if len(board) >= limit: break
    for i, b in enumerate(board): b["rank"] = i + 1
    return {"year": year or "all-time", "leaderboard": board}

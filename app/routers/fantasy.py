"""
T20 Fantasy Season Challenge — Streamlined CRUD
Flow: Find Match → Browse Players → Build XI → Submit Entry → REVEAL
"""
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


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

async def score_player(player_name: str, match_id: int, role: str, session: AsyncSession) -> dict:
    """Score a player from ball-by-ball data for a specific match"""

    bat = (await session.execute(
        select(
            func.sum(Delivery.runs_batter).label("runs"),
            func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
            func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes"),
            func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
            func.count(Delivery.id).filter(Delivery.is_wicket == True).label("dismissed"),
        ).where(Delivery.match_id == match_id, Delivery.batter == player_name)
    )).first()

    runs = bat.runs or 0
    fours = bat.fours or 0
    sixes = bat.sixes or 0
    balls_faced = bat.balls or 0
    dismissed = (bat.dismissed or 0) > 0

    bat_pts = runs + fours + (sixes * 2)
    bat_bonuses = []
    if runs >= 50:
        bat_pts += 20
        bat_bonuses.append("50+ bonus (+20)")
    elif runs >= 30:
        bat_pts += 10
        bat_bonuses.append("30+ bonus (+10)")
    if runs == 0 and dismissed:
        bat_pts -= 5
        bat_bonuses.append("duck (-5)")

    bowl = (await session.execute(
        select(
            func.count(Delivery.id).filter(Delivery.is_wicket == True).label("wickets"),
            func.sum(Delivery.runs_total).label("runs_conceded"),
            func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls_bowled"),
        ).where(Delivery.match_id == match_id, Delivery.bowler == player_name)
    )).first()

    wickets = bowl.wickets or 0
    runs_conceded = bowl.runs_conceded or 0
    balls_bowled = bowl.balls_bowled or 0
    economy = round((runs_conceded / balls_bowled) * 6, 2) if balls_bowled > 0 else 0.0

    bowl_pts = wickets * 25
    bowl_bonuses = []
    if wickets >= 4:
        bowl_pts += 20
        bowl_bonuses.append("4+ wickets (+20)")
    elif wickets >= 3:
        bowl_pts += 10
        bowl_bonuses.append("3 wickets (+10)")
    if balls_bowled >= 6:
        if economy < 6:
            bowl_pts += 6
            bowl_bonuses.append("economy <6 (+6)")
        elif economy < 7:
            bowl_pts += 4
            bowl_bonuses.append("economy 6-7 (+4)")
        elif economy < 8:
            bowl_pts += 2
            bowl_bonuses.append("economy 7-8 (+2)")
        elif economy >= 10:
            bowl_pts -= 4
            bowl_bonuses.append("economy >10 (-4)")
        elif economy >= 9:
            bowl_pts -= 2
            bowl_bonuses.append("economy 9-10 (-2)")

    base_points = bat_pts + bowl_pts
    multiplier = 2.0 if role == "CAPTAIN" else 1.5 if role == "VICE_CAPTAIN" else 1.0
    final_points = round(base_points * multiplier, 1)

    return {
        "player": player_name,
        "role": role,
        "batting": {
            "runs": runs, "balls_faced": balls_faced,
            "fours": fours, "sixes": sixes,
            "dismissed": dismissed, "bonuses": bat_bonuses, "points": bat_pts,
        },
        "bowling": {
            "wickets": wickets, "balls_bowled": balls_bowled,
            "economy": economy, "bonuses": bowl_bonuses, "points": bowl_pts,
        },
        "base_points": base_points,
        "multiplier": multiplier,
        "final_points": final_points,
        "explain": (
            f"Bat: {runs}r+{fours}×4+{sixes}×6={bat_pts}pts | "
            f"Bowl: {wickets}w@{economy}={bowl_pts}pts | "
            f"Base {base_points}×{multiplier}({role})={final_points}pts"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — FIND MATCH → returns match_key (the match id)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/match")
async def find_match(
    team1: Optional[str] = Query(None, description="e.g. India"),
    team2: Optional[str] = Query(None, description="e.g. England"),
    year: Optional[str] = Query(None, description="e.g. 2024"),
    stage: Optional[str] = Query(None, description="e.g. Final, Semi Final, Group"),
    date: Optional[str] = Query(None, description="e.g. 2024-06-27"),
    session: AsyncSession = Depends(get_session),
):
    """
    STEP 1 — Find a match to build your Fantasy XI for.
    Returns match_key (id) to use in next steps.
    Winner is always hidden — anti-spoiler.

    Example: GET /fantasy/match?team1=India&team2=England&year=2024
    """
    query = select(Match)

    if team1 and team2:
        query = query.where(
            ((Match.team1 == team1) & (Match.team2 == team2)) |
            ((Match.team1 == team2) & (Match.team2 == team1))
        )
    elif team1:
        query = query.where((Match.team1 == team1) | (Match.team2 == team1))
    elif team2:
        query = query.where((Match.team1 == team2) | (Match.team2 == team2))

    if year:
        query = query.where(Match.tournament_year == year)
    if stage:
        query = query.where(Match.stage.ilike(f"%{stage}%"))
    if date:
        query = query.where(Match.match_date == date)

    matches = (await session.execute(
        query.order_by(Match.match_date.desc()).limit(20)
    )).scalars().all()

    if not matches:
        raise HTTPException(
            status_code=404,
            detail="No matches found. Try different filters. Available years: 2014, 2016, 2021, 2022, 2024, 2026"
        )

    return {
        "total": len(matches),
        "next_step": "Copy a match_key and use GET /fantasy/match/{match_key}/players",
        "matches": [
            {
                "match_key": m.id,
                "matchup": f"{m.team1} vs {m.team2}",
                "year": m.tournament_year,
                "date": str(m.match_date),
                "venue": m.venue,
                "stage": m.stage or "Group Stage",
            }
            for m in matches
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — BROWSE PLAYERS → returns player_keys to pick from
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/match/{match_key}/players")
async def get_match_players(
    match_key: int,
    session: AsyncSession = Depends(get_session),
):
    """
    STEP 2 — See all players available for this match.
    Returns player_key (name) + estimated fantasy points.
    Pick 11 player_keys for your team.
    """
    match = await session.get(Match, match_key)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    batters_q = (await session.execute(
        select(
            Delivery.batter,
            Delivery.batting_team,
            func.sum(Delivery.runs_batter).label("runs"),
            func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
            func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
            func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes"),
            func.count(Delivery.id).filter(Delivery.is_wicket == True).label("dismissed"),
        )
        .where(Delivery.match_id == match_key)
        .group_by(Delivery.batter, Delivery.batting_team)
    )).all()

    bowlers_q = (await session.execute(
        select(
            Delivery.bowler,
            Delivery.bowling_team,
            func.count(Delivery.id).filter(Delivery.is_wicket == True).label("wickets"),
            func.sum(Delivery.runs_total).label("runs_conceded"),
            func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
        )
        .where(Delivery.match_id == match_key)
        .group_by(Delivery.bowler, Delivery.bowling_team)
    )).all()

    player_map = {}

    for b in batters_q:
        runs = b.runs or 0
        balls = b.balls or 1
        fours = b.fours or 0
        sixes = b.sixes or 0
        dismissed = (b.dismissed or 0) > 0
        bat_pts = runs + fours + (sixes * 2)
        if runs >= 50: bat_pts += 20
        elif runs >= 30: bat_pts += 10
        if runs == 0 and dismissed: bat_pts -= 5

        player_map[b.batter] = {
            "player_key": b.batter,
            "team": b.batting_team,
            "batting": {
                "runs": runs,
                "balls": b.balls or 0,
                "strike_rate": round(runs / balls * 100, 1),
                "fours": fours,
                "sixes": sixes,
            },
            "bowling": {"wickets": 0, "economy": 0},
            "bat_pts": bat_pts,
            "bowl_pts": 0,
            "estimated_points": bat_pts,
        }

    for b in bowlers_q:
        balls = b.balls or 1
        runs = b.runs_conceded or 0
        economy = round(runs / balls * 6, 2)
        wickets = b.wickets or 0
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
            player_map[b.bowler]["bowling"] = {"wickets": wickets, "economy": economy}
            player_map[b.bowler]["bowl_pts"] = bowl_pts
            player_map[b.bowler]["estimated_points"] += bowl_pts
        else:
            player_map[b.bowler] = {
                "player_key": b.bowler,
                "team": b.bowling_team,
                "batting": {"runs": 0, "balls": 0, "strike_rate": 0, "fours": 0, "sixes": 0},
                "bowling": {"wickets": wickets, "economy": economy},
                "bat_pts": 0,
                "bowl_pts": bowl_pts,
                "estimated_points": bowl_pts,
            }

    players = sorted(player_map.values(), key=lambda x: x["estimated_points"], reverse=True)
    team1_players = [p for p in players if p["team"] == match.team1]
    team2_players = [p for p in players if p["team"] == match.team2]

    return {
        "match_key": match_key,
        "matchup": f"{match.team1} vs {match.team2}",
        "date": str(match.match_date),
        "year": match.tournament_year,
        "stage": match.stage,
        "instructions": (
            f"Pick 11 player_keys below. "
            f"Use POST /fantasy/teams to create your XI. "
            f"Set 1 CAPTAIN (×2pts) and 1 VICE_CAPTAIN (×1.5pts)."
        ),
        "players": {
            match.team1: [
                {
                    "rank": i + 1,
                    "player_key": p["player_key"],
                    "estimated_pts": round(p["estimated_points"], 1),
                    "batting": p["batting"],
                    "bowling": p["bowling"],
                }
                for i, p in enumerate(team1_players)
            ],
            match.team2: [
                {
                    "rank": i + 1,
                    "player_key": p["player_key"],
                    "estimated_pts": round(p["estimated_points"], 1),
                    "batting": p["batting"],
                    "bowling": p["bowling"],
                }
                for i, p in enumerate(team2_players)
            ],
        },
        "all_players_ranked": [
            {
                "rank": i + 1,
                "player_key": p["player_key"],
                "team": p["team"],
                "estimated_pts": round(p["estimated_points"], 1),
            }
            for i, p in enumerate(players)
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FANTASY TEAMS — Full CRUD
# POST   /fantasy/teams
# GET    /fantasy/teams
# GET    /fantasy/teams/{team_id}
# PUT    /fantasy/teams/{team_id}
# DELETE /fantasy/teams/{team_id}
# POST   /fantasy/teams/{team_id}/players
# DELETE /fantasy/teams/{team_id}/players/{player_key}
# PUT    /fantasy/teams/{team_id}/captain
# PUT    /fantasy/teams/{team_id}/vice-captain
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/teams", status_code=status.HTTP_201_CREATED)
async def create_team(
    team_name: str = Form(..., description="Your team name"),
    match_key: int = Form(..., description="match_key from GET /fantasy/match"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    STEP 3a — Create your Fantasy XI shell.
    Use match_key from GET /fantasy/match.
    Then add players via POST /fantasy/teams/{team_id}/players
    """
    match = await session.get(Match, match_key)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match {match_key} not found")

    team = FantasyTeam(
        user_id=current_user.id,
        team_name=team_name,
    )
    session.add(team)
    await session.commit()
    await session.refresh(team)

    return {
        "team_id": team.id,
        "team_name": team.team_name,
        "match": f"{match.team1} vs {match.team2} ({match.tournament_year})",
        "match_key": match_key,
        "players_added": 0,
        "next_steps": [
            f"POST /fantasy/teams/{team.id}/players?player_key=RG Sharma&match_key={match_key} (repeat ×11)",
            f"PUT /fantasy/teams/{team.id}/captain?player_key=RG Sharma",
            f"PUT /fantasy/teams/{team.id}/vice-captain?player_key=V Kohli",
            f"GET /fantasy/teams/{team.id} to verify your XI",
        ],
    }


@router.post("/teams/{team_id}/players", status_code=status.HTTP_201_CREATED)
async def add_player(
    team_id: int,
    player_key: str = Query(..., description="player_key from GET /fantasy/match/{match_key}/players"),
    match_key: int = Query(..., description="match_key to validate player played in this match"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    STEP 3b — Add a player to your XI.
    Call this 11 times with different player_keys.
    player_key must be from GET /fantasy/match/{match_key}/players
    """
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    match = await session.get(Match, match_key)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Check max 11 players
    current_count = (await session.execute(
        select(func.count(FantasyTeamPlayer.id))
        .where(FantasyTeamPlayer.fantasy_team_id == team_id)
    )).scalar() or 0
    if current_count >= 11:
        raise HTTPException(status_code=400, detail="Already have 11 players. Remove one first.")

    # Check no duplicates
    existing_player = (await session.execute(
        select(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team_id,
            FantasyTeamPlayer.player_name == player_key,
        )
    )).scalar_one_or_none()
    if existing_player:
        raise HTTPException(status_code=400, detail=f"{player_key} is already in your team")

    # Validate player played in this match
    played = (await session.execute(
        select(Delivery.batter).where(
            Delivery.match_id == match_key,
            Delivery.batter == player_key,
        ).limit(1)
    )).scalar()
    bowled = (await session.execute(
        select(Delivery.bowler).where(
            Delivery.match_id == match_key,
            Delivery.bowler == player_key,
        ).limit(1)
    )).scalar()
    if not played and not bowled:
        raise HTTPException(
            status_code=400,
            detail=f"'{player_key}' did not play in this match. Check GET /fantasy/match/{match_key}/players"
        )

    session.add(FantasyTeamPlayer(
        fantasy_team_id=team_id,
        player_name=player_key,
        tournament_year=match.tournament_year,
        role="PLAYER",
        order=current_count,
    ))
    await session.commit()

    new_count = current_count + 1
    return {
        "team_id": team_id,
        "team_name": team.team_name,
        "added": player_key,
        "players_added": new_count,
        "players_remaining": 11 - new_count,
        "message": (
            f"✅ {player_key} added. {11 - new_count} more to go."
            if new_count < 11
            else "✅ XI complete! Now set your captain and vice captain."
        ),
    }


@router.delete("/teams/{team_id}/players/{player_key:path}", status_code=status.HTTP_200_OK)
async def remove_player(
    team_id: int,
    player_key: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Remove a player from your XI"""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    player = (await session.execute(
        select(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team_id,
            FantasyTeamPlayer.player_name == player_key,
        )
    )).scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail=f"{player_key} not in this team")

    await session.delete(player)
    await session.commit()

    count = (await session.execute(
        select(func.count(FantasyTeamPlayer.id))
        .where(FantasyTeamPlayer.fantasy_team_id == team_id)
    )).scalar() or 0

    return {
        "message": f"✅ {player_key} removed",
        "players_remaining_in_team": count,
    }


@router.put("/teams/{team_id}/captain")
async def set_captain(
    team_id: int,
    player_key: str = Query(..., description="Player to make captain"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Set captain (2x points). Player must already be in your XI."""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Remove existing captain
    existing_captain = (await session.execute(
        select(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team_id,
            FantasyTeamPlayer.role == "CAPTAIN",
        )
    )).scalar_one_or_none()
    if existing_captain:
        existing_captain.role = "PLAYER"

    # Set new captain
    new_captain = (await session.execute(
        select(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team_id,
            FantasyTeamPlayer.player_name == player_key,
        )
    )).scalar_one_or_none()
    if not new_captain:
        raise HTTPException(
            status_code=400,
            detail=f"{player_key} is not in your team. Add them first."
        )
    if new_captain.role == "VICE_CAPTAIN":
        raise HTTPException(
            status_code=400,
            detail=f"{player_key} is already your vice captain. Choose someone else."
        )

    new_captain.role = "CAPTAIN"
    await session.commit()

    return {
        "message": f"⭐ {player_key} is now your CAPTAIN (×2 points)",
        "team_id": team_id,
    }


@router.put("/teams/{team_id}/vice-captain")
async def set_vice_captain(
    team_id: int,
    player_key: str = Query(..., description="Player to make vice captain"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Set vice captain (1.5x points). Player must already be in your XI."""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    existing_vc = (await session.execute(
        select(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team_id,
            FantasyTeamPlayer.role == "VICE_CAPTAIN",
        )
    )).scalar_one_or_none()
    if existing_vc:
        existing_vc.role = "PLAYER"

    new_vc = (await session.execute(
        select(FantasyTeamPlayer).where(
            FantasyTeamPlayer.fantasy_team_id == team_id,
            FantasyTeamPlayer.player_name == player_key,
        )
    )).scalar_one_or_none()
    if not new_vc:
        raise HTTPException(
            status_code=400,
            detail=f"{player_key} is not in your team. Add them first."
        )
    if new_vc.role == "CAPTAIN":
        raise HTTPException(
            status_code=400,
            detail=f"{player_key} is already your captain. Choose someone else."
        )

    new_vc.role = "VICE_CAPTAIN"
    await session.commit()

    return {
        "message": f"🔵 {player_key} is now your VICE CAPTAIN (×1.5 points)",
        "team_id": team_id,
    }


@router.get("/teams")
async def list_teams(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all your Fantasy XIs"""
    teams = (await session.execute(
        select(FantasyTeam).where(FantasyTeam.user_id == current_user.id)
        .order_by(FantasyTeam.created_at.desc())
    )).scalars().all()

    result = []
    for t in teams:
        players = (await session.execute(
            select(FantasyTeamPlayer)
            .where(FantasyTeamPlayer.fantasy_team_id == t.id)
            .order_by(FantasyTeamPlayer.order)
        )).scalars().all()
        captain = next((p.player_name for p in players if p.role == "CAPTAIN"), None)
        vc = next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None)
        result.append({
            "team_id": t.id,
            "team_name": t.team_name,
            "players_added": len(players),
            "complete": len(players) == 11,
            "captain": captain or "⚠️ Not set",
            "vice_captain": vc or "⚠️ Not set",
            "ready": len(players) == 11 and captain and vc,
        })

    return {"total": len(result), "teams": result}


@router.get("/teams/{team_id}")
async def get_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """View your Fantasy XI with full player list and readiness check"""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    players = (await session.execute(
        select(FantasyTeamPlayer)
        .where(FantasyTeamPlayer.fantasy_team_id == team_id)
        .order_by(FantasyTeamPlayer.order)
    )).scalars().all()

    captain = next((p.player_name for p in players if p.role == "CAPTAIN"), None)
    vc = next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None)
    ready = len(players) == 11 and captain and vc

    warnings = []
    if len(players) < 11:
        warnings.append(f"Need {11 - len(players)} more players")
    if not captain:
        warnings.append("No captain set — PUT /fantasy/teams/{team_id}/captain")
    if not vc:
        warnings.append("No vice captain set — PUT /fantasy/teams/{team_id}/vice-captain")

    return {
        "team_id": team.id,
        "team_name": team.team_name,
        "ready_to_submit": ready,
        "warnings": warnings,
        "captain": captain or "⚠️ Not set",
        "vice_captain": vc or "⚠️ Not set",
        "squad": [
            {
                "player_key": p.player_name,
                "role": p.role,
                "year": p.tournament_year,
            }
            for p in players
        ],
        "next_step": f"POST /fantasy/entries?fantasy_team_id={team_id}&match_key=<match_key>" if ready else "Complete your XI first",
    }


@router.put("/teams/{team_id}")
async def rename_team(
    team_id: int,
    team_name: str = Form(..., description="New team name"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Rename your Fantasy XI"""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    old_name = team.team_name
    team.team_name = team_name.strip()
    await session.commit()

    return {
        "message": f"✅ Renamed '{old_name}' → '{team.team_name}'",
        "team_id": team_id,
    }


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete your Fantasy XI and all its entries"""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    await session.delete(team)
    await session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# FANTASY ENTRIES — Full CRUD + REVEAL
# POST   /fantasy/entries
# GET    /fantasy/entries
# GET    /fantasy/entries/{entry_id}
# PUT    /fantasy/entries/{entry_id}
# DELETE /fantasy/entries/{entry_id}
# POST   /fantasy/entries/{entry_id}/submit
# POST   /fantasy/entries/{entry_id}/reveal  ← FLAGSHIP
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/entries", status_code=status.HTTP_201_CREATED)
async def create_entry(
    fantasy_team_id: int = Query(..., description="team_id from GET /fantasy/teams"),
    match_key: int = Query(..., description="match_key from GET /fantasy/match"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    STEP 4 — Enter your Fantasy XI into a match.
    Team must be complete (11 players + captain + vice captain).
    Status = DRAFT. Use /submit to lock it in.
    """
    match = await session.get(Match, match_key)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == fantasy_team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")

    # Validate team is complete
    players = (await session.execute(
        select(FantasyTeamPlayer)
        .where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
    )).scalars().all()

    if len(players) != 11:
        raise HTTPException(
            status_code=400,
            detail=f"Team has {len(players)} players — need exactly 11"
        )
    if not any(p.role == "CAPTAIN" for p in players):
        raise HTTPException(status_code=400, detail="No captain set")
    if not any(p.role == "VICE_CAPTAIN" for p in players):
        raise HTTPException(status_code=400, detail="No vice captain set")

    # No duplicate entries
    existing = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.user_id == current_user.id,
            FantasyEntry.match_id == match_key,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Already entered this match. Entry ID: {existing.id}"
        )

    entry = FantasyEntry(
        user_id=current_user.id,
        match_id=match_key,
        fantasy_team_id=fantasy_team_id,
        status="DRAFT",
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    captain = next((p.player_name for p in players if p.role == "CAPTAIN"), None)
    vc = next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None)

    return {
        "entry_id": entry.id,
        "status": "DRAFT",
        "match": f"{match.team1} vs {match.team2} ({match.match_date})",
        "match_key": match_key,
        "fantasy_team": team.team_name,
        "captain": captain,
        "vice_captain": vc,
        "next_steps": [
            f"POST /fantasy/entries/{entry.id}/submit — lock your entry",
            f"PUT /fantasy/entries/{entry.id}?fantasy_team_id=... — swap team while DRAFT",
            f"DELETE /fantasy/entries/{entry.id} — withdraw",
        ],
    }


@router.post("/entries/{entry_id}/submit")
async def submit_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Lock your entry. Cannot edit after submit. Then use /reveal to score."""
    entry = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.id == entry_id,
            FantasyEntry.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != "DRAFT":
        raise HTTPException(status_code=400, detail=f"Entry is already {entry.status}")

    entry.status = "SUBMITTED"
    await session.commit()

    return {
        "entry_id": entry.id,
        "status": "SUBMITTED",
        "message": "Entry locked ✅",
        "next_step": f"POST /fantasy/entries/{entry_id}/reveal to score your XI ⭐",
    }


@router.get("/entries")
async def list_entries(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Your full entry history"""
    entries = (await session.execute(
        select(FantasyEntry).where(FantasyEntry.user_id == current_user.id)
        .order_by(FantasyEntry.created_at.desc())
    )).scalars().all()

    result = []
    for e in entries:
        match = await session.get(Match, e.match_id)
        team = await session.get(FantasyTeam, e.fantasy_team_id)
        result.append({
            "entry_id": e.id,
            "match": f"{match.team1} vs {match.team2} ({match.match_date})" if match else None,
            "year": match.tournament_year if match else None,
            "fantasy_team": team.team_name if team else None,
            "status": e.status,
            "total_points": e.total_points,
            "rank_global": e.rank_global,
        })

    revealed = [e for e in entries if e.status == "REVEALED"]
    return {
        "total_entries": len(entries),
        "revealed": len(revealed),
        "best_score": max((e.total_points for e in revealed if e.total_points), default=None),
        "entries": result,
    }


@router.get("/entries/{entry_id}")
async def get_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """View entry — full breakdown shown if revealed"""
    entry = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.id == entry_id,
            FantasyEntry.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    match = await session.get(Match, entry.match_id)
    team = await session.get(FantasyTeam, entry.fantasy_team_id)

    response = {
        "entry_id": entry.id,
        "match": f"{match.team1} vs {match.team2} ({match.match_date})",
        "fantasy_team": team.team_name if team else None,
        "status": entry.status,
        "total_points": entry.total_points,
        "rank_global": entry.rank_global,
    }
    if entry.status == "REVEALED" and entry.breakdown:
        response["actual_winner"] = match.winner
        response["breakdown"] = entry.breakdown
    return response


@router.put("/entries/{entry_id}")
async def update_entry(
    entry_id: int,
    fantasy_team_id: int = Query(..., description="Swap to a different team"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Swap your fantasy team — only while status is DRAFT"""
    entry = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.id == entry_id,
            FantasyEntry.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit — entry is {entry.status}. Only DRAFT entries can be changed."
        )

    new_team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == fantasy_team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not new_team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")

    entry.fantasy_team_id = fantasy_team_id
    await session.commit()

    return {
        "message": f"✅ Swapped to team '{new_team.team_name}'",
        "entry_id": entry_id,
        "status": entry.status,
    }


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Withdraw entry — only before reveal"""
    entry = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.id == entry_id,
            FantasyEntry.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == "REVEALED":
        raise HTTPException(status_code=400, detail="Cannot delete a revealed entry")
    await session.delete(entry)
    await session.commit()


@router.post("/entries/{entry_id}/reveal")
async def reveal_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    ⭐ FLAGSHIP — Score your Fantasy XI from ball-by-ball data.
    Captain gets 2x. Vice Captain gets 1.5x.
    Reveals match winner. Shows full player breakdown.
    Calculates your global rank for this match.
    """
    entry = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.id == entry_id,
            FantasyEntry.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == "REVEALED":
        raise HTTPException(status_code=400, detail="Already revealed")
    if entry.status == "DRAFT":
        raise HTTPException(
            status_code=400,
            detail=f"Submit your entry first — POST /fantasy/entries/{entry_id}/submit"
        )

    match = await session.get(Match, entry.match_id)
    team = await session.get(FantasyTeam, entry.fantasy_team_id)
    players = (await session.execute(
        select(FantasyTeamPlayer)
        .where(FantasyTeamPlayer.fantasy_team_id == entry.fantasy_team_id)
        .order_by(FantasyTeamPlayer.order)
    )).scalars().all()

    # Score every player from real ball-by-ball data
    breakdown = []
    total_points = 0.0
    for p in players:
        scored = await score_player(p.player_name, entry.match_id, p.role, session)
        breakdown.append(scored)
        total_points += scored["final_points"]
    total_points = round(total_points, 1)

    # Calculate global rank for this match
    others = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.match_id == entry.match_id,
            FantasyEntry.status == "REVEALED",
        )
    )).scalars().all()
    rank = sum(1 for e in others if (e.total_points or 0) > total_points) + 1

    # Save
    entry.status = "REVEALED"
    entry.total_points = total_points
    entry.rank_global = rank
    entry.breakdown = breakdown
    await session.commit()

    # Pretty summary for demo
    pretty = []
    for b in breakdown:
        icon = "⭐" if b["role"] == "CAPTAIN" else "🔵" if b["role"] == "VICE_CAPTAIN" else "  "
        pretty.append(
            f"{icon} {b['player']} ({b['role']}) → "
            f"{b['batting']['runs']}r {b['bowling']['wickets']}w → "
            f"{b['base_points']} × {b['multiplier']} = {b['final_points']}pts"
        )
    pretty.append("━" * 50)
    pretty.append(f"TOTAL: {total_points} Fantasy Points | Global Rank #{rank}")

    return {
        "entry_id": entry.id,
        "match": f"{match.team1} vs {match.team2} ({match.match_date})",
        "actual_winner": match.winner,
        "fantasy_team": team.team_name if team else None,
        "status": "REVEALED",
        "total_points": total_points,
        "rank_global": rank,
        "total_players_entered": len(others) + 1,
        "breakdown": breakdown,
        "pretty_summary": pretty,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/leaderboard/{match_key}")
async def match_leaderboard(
    match_key: int,
    limit: int = Query(10),
    session: AsyncSession = Depends(get_session),
):
    """Leaderboard for a specific match"""
    match = await session.get(Match, match_key)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    entries = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.match_id == match_key,
            FantasyEntry.status == "REVEALED",
        ).order_by(FantasyEntry.total_points.desc()).limit(limit)
    )).scalars().all()

    board = []
    for i, e in enumerate(entries):
        user = await session.get(User, e.user_id)
        team = await session.get(FantasyTeam, e.fantasy_team_id)
        board.append({
            "rank": i + 1,
            "username": user.username if user else "Unknown",
            "fantasy_team": team.team_name if team else None,
            "total_points": e.total_points,
        })

    return {
        "match": f"{match.team1} vs {match.team2} ({match.match_date})",
        "actual_winner": match.winner,
        "total_entries": len(entries),
        "leaderboard": board,
    }


@router.get("/leaderboard")
async def global_leaderboard(
    year: Optional[str] = Query(None),
    limit: int = Query(10),
    session: AsyncSession = Depends(get_session),
):
    """Global fantasy leaderboard across all matches"""
    entries = (await session.execute(
        select(FantasyEntry).where(FantasyEntry.status == "REVEALED")
        .order_by(FantasyEntry.total_points.desc())
    )).scalars().all()

    board = []
    seen = set()
    for e in entries:
        match = await session.get(Match, e.match_id)
        if year and match and match.tournament_year != year:
            continue
        user = await session.get(User, e.user_id)
        team = await session.get(FantasyTeam, e.fantasy_team_id)
        board.append({
            "username": user.username if user else "Unknown",
            "fantasy_team": team.team_name if team else None,
            "match": f"{match.team1} vs {match.team2}" if match else None,
            "year": match.tournament_year if match else None,
            "total_points": e.total_points,
        })
        if len(board) >= limit:
            break

    for i, b in enumerate(board):
        b["rank"] = i + 1

    return {
        "year": year or "all-time",
        "leaderboard": board,
    } 
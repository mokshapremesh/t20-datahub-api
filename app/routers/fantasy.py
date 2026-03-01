from fastapi import APIRouter, Depends, HTTPException, status, Query
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

async def score_player(
    player_name: str,
    match_id: int,
    role: str,
    session: AsyncSession
) -> dict:
    """Score a single player from ball-by-ball deliveries for a specific match"""

    # ── Batting ───────────────────────────────────────────────────────────────
    bat_q = await session.execute(
        select(
            func.sum(Delivery.runs_batter).label("runs"),
            func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
            func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes"),
            func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
            func.count(Delivery.id).filter(Delivery.is_wicket == True).label("dismissed"),
        ).where(
            Delivery.match_id == match_id,
            Delivery.batter == player_name,
        )
    )
    bat = bat_q.first()
    runs  = bat.runs or 0
    fours = bat.fours or 0
    sixes = bat.sixes or 0
    balls_faced = bat.balls or 0
    dismissed = (bat.dismissed or 0) > 0

    # Batting points
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
        bat_bonuses.append("duck penalty (-5)")

    # ── Bowling ───────────────────────────────────────────────────────────────
    bowl_q = await session.execute(
        select(
            func.count(Delivery.id).filter(Delivery.is_wicket == True).label("wickets"),
            func.sum(Delivery.runs_total).label("runs_conceded"),
            func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls_bowled"),
        ).where(
            Delivery.match_id == match_id,
            Delivery.bowler == player_name,
        )
    )
    bowl = bowl_q.first()
    wickets      = bowl.wickets or 0
    runs_conceded = bowl.runs_conceded or 0
    balls_bowled  = bowl.balls_bowled or 0
    economy = round((runs_conceded / balls_bowled) * 6, 2) if balls_bowled > 0 else 0.0

    # Bowling points
    bowl_pts = wickets * 25
    bowl_bonuses = []

    if wickets >= 4:
        bowl_pts += 20
        bowl_bonuses.append("4+ wickets bonus (+20)")
    elif wickets >= 3:
        bowl_pts += 10
        bowl_bonuses.append("3 wickets bonus (+10)")

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
        elif economy < 9:
            pass
        elif economy < 10:
            bowl_pts -= 2
            bowl_bonuses.append("economy 9-10 (-2)")
        else:
            bowl_pts -= 4
            bowl_bonuses.append("economy >10 (-4)")

    # ── Apply role multiplier ─────────────────────────────────────────────────
    base_points = bat_pts + bowl_pts
    multiplier = 2.0 if role == "CAPTAIN" else 1.5 if role == "VICE_CAPTAIN" else 1.0
    final_points = round(base_points * multiplier, 1)

    # Build explain string
    explain_parts = []
    if runs > 0 or balls_faced > 0:
        explain_parts.append(
            f"Batting: {runs} runs (+{runs}) + {fours} fours (+{fours}) + "
            f"{sixes} sixes (+{sixes*2})"
        )
        if bat_bonuses:
            explain_parts.append(f"Batting bonuses: {', '.join(bat_bonuses)}")
    if balls_bowled > 0:
        explain_parts.append(
            f"Bowling: {wickets} wickets (+{wickets*25}) @ economy {economy}"
        )
        if bowl_bonuses:
            explain_parts.append(f"Bowling bonuses: {', '.join(bowl_bonuses)}")
    explain_parts.append(
        f"Base: {base_points} pts × {multiplier} ({role}) = {final_points} pts"
    )

    return {
        "player": player_name,
        "role": role,
        "batting": {
            "runs": runs,
            "balls_faced": balls_faced,
            "fours": fours,
            "sixes": sixes,
            "dismissed": dismissed,
            "bonuses": bat_bonuses,
            "points": bat_pts,
        },
        "bowling": {
            "wickets": wickets,
            "balls_bowled": balls_bowled,
            "runs_conceded": runs_conceded,
            "economy": economy,
            "bonuses": bowl_bonuses,
            "points": bowl_pts,
        },
        "base_points": base_points,
        "multiplier": multiplier,
        "final_points": final_points,
        "explain": " | ".join(explain_parts),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# A) FANTASY TEAMS — Full CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/teams", status_code=status.HTTP_201_CREATED)
async def create_fantasy_team(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Fantasy XI.
    Exactly 11 players required. Exactly 1 CAPTAIN and 1 VICE_CAPTAIN.

    Body:
    {
        "team_name": "My Dream XI",
        "players": [
            {"player_name": "V Kohli", "tournament_year": "2024", "role": "CAPTAIN"},
            {"player_name": "JJ Bumrah", "tournament_year": "2024", "role": "VICE_CAPTAIN"},
            {"player_name": "RG Sharma", "tournament_year": "2024", "role": "PLAYER"},
            ... 8 more PLAYER entries
        ]
    }
    """
    team_name = body.get("team_name", "").strip()
    players = body.get("players", [])

    if not team_name:
        raise HTTPException(status_code=400, detail="team_name is required")
    if len(players) != 11:
        raise HTTPException(status_code=400, detail="Exactly 11 players required")

    roles = [p.get("role", "PLAYER") for p in players]
    if roles.count("CAPTAIN") != 1:
        raise HTTPException(status_code=400, detail="Exactly 1 CAPTAIN required")
    if roles.count("VICE_CAPTAIN") != 1:
        raise HTTPException(status_code=400, detail="Exactly 1 VICE_CAPTAIN required")

    valid_roles = {"CAPTAIN", "VICE_CAPTAIN", "PLAYER"}
    for p in players:
        if p.get("role", "PLAYER") not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role: {p.get('role')}")
        if not p.get("player_name") or not p.get("tournament_year"):
            raise HTTPException(status_code=400, detail="Each player needs player_name and tournament_year")

    team = FantasyTeam(user_id=current_user.id, team_name=team_name)
    session.add(team)
    await session.flush()

    for i, p in enumerate(players):
        session.add(FantasyTeamPlayer(
            fantasy_team_id=team.id,
            player_name=p["player_name"],
            tournament_year=p["tournament_year"],
            role=p.get("role", "PLAYER"),
            order=i,
        ))

    await session.commit()
    await session.refresh(team)

    return {
        "id": team.id,
        "team_name": team.team_name,
        "players": [
            {"player_name": p["player_name"], "year": p["tournament_year"], "role": p.get("role", "PLAYER")}
            for p in players
        ],
        "message": f"Fantasy XI '{team_name}' created. Submit it for a match at POST /fantasy/matches/{{match_id}}/entries",
    }


@router.get("/teams")
async def list_fantasy_teams(
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
            select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == t.id)
            .order_by(FantasyTeamPlayer.order)
        )).scalars().all()
        captain = next((p.player_name for p in players if p.role == "CAPTAIN"), None)
        vice = next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None)
        result.append({
            "id": t.id,
            "team_name": t.team_name,
            "captain": captain,
            "vice_captain": vice,
            "players": [p.player_name for p in players],
            "created_at": str(t.created_at),
        })

    return {"total": len(result), "teams": result}


@router.get("/teams/{team_id}")
async def get_fantasy_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a single Fantasy XI with full player details"""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")

    players = (await session.execute(
        select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id)
        .order_by(FantasyTeamPlayer.order)
    )).scalars().all()

    return {
        "id": team.id,
        "team_name": team.team_name,
        "created_at": str(team.created_at),
        "players": [
            {
                "id": p.id,
                "player_name": p.player_name,
                "tournament_year": p.tournament_year,
                "role": p.role,
            }
            for p in players
        ],
        "captain": next((p.player_name for p in players if p.role == "CAPTAIN"), None),
        "vice_captain": next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None),
    }


@router.put("/teams/{team_id}")
async def update_fantasy_team(
    team_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Update team name or swap players.
    Provide team_name to rename.
    Provide players array to replace full XI.
    """
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")

    if "team_name" in body:
        team.team_name = body["team_name"].strip()

    if "players" in body:
        players = body["players"]
        if len(players) != 11:
            raise HTTPException(status_code=400, detail="Exactly 11 players required")
        roles = [p.get("role", "PLAYER") for p in players]
        if roles.count("CAPTAIN") != 1:
            raise HTTPException(status_code=400, detail="Exactly 1 CAPTAIN required")
        if roles.count("VICE_CAPTAIN") != 1:
            raise HTTPException(status_code=400, detail="Exactly 1 VICE_CAPTAIN required")

        # Delete existing players
        existing = (await session.execute(
            select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id)
        )).scalars().all()
        for p in existing:
            await session.delete(p)
        await session.flush()

        for i, p in enumerate(players):
            session.add(FantasyTeamPlayer(
                fantasy_team_id=team_id,
                player_name=p["player_name"],
                tournament_year=p["tournament_year"],
                role=p.get("role", "PLAYER"),
                order=i,
            ))

    await session.commit()
    return {"message": "Team updated", "id": team_id, "team_name": team.team_name}


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fantasy_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a Fantasy XI and all its entries"""
    team = (await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")
    await session.delete(team)
    await session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# B) FANTASY ENTRIES — Submit XI for a match + REVEAL
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/matches")
async def browse_matches(
    year: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    limit: int = Query(20),
    session: AsyncSession = Depends(get_session),
):
    """Browse matches to submit your Fantasy XI for. Winner hidden — anti-spoiler."""
    query = select(Match)
    if year:
        query = query.where(Match.tournament_year == year)
    if team:
        query = query.where((Match.team1 == team) | (Match.team2 == team))
    if stage:
        query = query.where(Match.stage == stage)

    matches = (await session.execute(
        query.order_by(Match.match_date.desc()).limit(limit)
    )).scalars().all()

    return {
        "total": len(matches),
        "note": "Winner hidden until you reveal your entry",
        "matches": [
            {
                "id": m.id,
                "team1": m.team1,
                "team2": m.team2,
                "date": str(m.match_date),
                "venue": m.venue,
                "stage": m.stage,
                "tournament_year": m.tournament_year,
            }
            for m in matches
        ],
    }


@router.post("/matches/{match_id}/entries", status_code=status.HTTP_201_CREATED)
async def submit_entry(
    match_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a Fantasy XI for a specific match.
    Body: { "fantasy_team_id": 1 }
    Status starts as SUBMITTED. Use POST /entries/{id}/reveal to score it.
    """
    fantasy_team_id = body.get("fantasy_team_id")
    if not fantasy_team_id:
        raise HTTPException(status_code=400, detail="fantasy_team_id required")

    match = await session.get(Match, match_id)
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

    # No duplicate entries per user per match
    existing = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.user_id == current_user.id,
            FantasyEntry.match_id == match_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Already entered this match. Entry ID: {existing.id}"
        )

    entry = FantasyEntry(
        user_id=current_user.id,
        match_id=match_id,
        fantasy_team_id=fantasy_team_id,
        status="SUBMITTED",
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)

    players = (await session.execute(
        select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == fantasy_team_id)
        .order_by(FantasyTeamPlayer.order)
    )).scalars().all()

    return {
        "entry_id": entry.id,
        "status": "SUBMITTED",
        "match": f"{match.team1} vs {match.team2} ({match.match_date})",
        "fantasy_team": team.team_name,
        "captain": next((p.player_name for p in players if p.role == "CAPTAIN"), None),
        "vice_captain": next((p.player_name for p in players if p.role == "VICE_CAPTAIN"), None),
        "players": [p.player_name for p in players],
        "next_step": f"POST /fantasy/entries/{entry.id}/reveal to score your XI",
    }


@router.get("/entries")
async def list_entries(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all your fantasy entries across all matches"""
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
            "tournament_year": match.tournament_year if match else None,
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
    """Get a single entry — shows full breakdown if revealed"""
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
        response["breakdown"] = entry.breakdown

    return response


@router.put("/entries/{entry_id}")
async def update_entry(
    entry_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Swap fantasy team before reveal — only allowed on SUBMITTED entries"""
    entry = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.id == entry_id,
            FantasyEntry.user_id == current_user.id,
        )
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status != "SUBMITTED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit — entry is already {entry.status}"
        )

    if "fantasy_team_id" in body:
        new_team = (await session.execute(
            select(FantasyTeam).where(
                FantasyTeam.id == body["fantasy_team_id"],
                FantasyTeam.user_id == current_user.id,
            )
        )).scalar_one_or_none()
        if not new_team:
            raise HTTPException(status_code=404, detail="Fantasy team not found")
        entry.fantasy_team_id = body["fantasy_team_id"]

    await session.commit()
    return {"message": "Entry updated", "entry_id": entry_id, "status": entry.status}


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete entry — only allowed before reveal"""
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
    ★ FLAGSHIP ENDPOINT ★
    Score your Fantasy XI from ball-by-ball deliveries.
    Captain gets 2x points. Vice captain gets 1.5x.
    Reveals match result. Calculates global rank.
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
    if entry.status != "SUBMITTED":
        raise HTTPException(status_code=400, detail="Entry must be SUBMITTED before reveal")

    match = await session.get(Match, entry.match_id)
    team = await session.get(FantasyTeam, entry.fantasy_team_id)

    players = (await session.execute(
        select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == entry.fantasy_team_id)
        .order_by(FantasyTeamPlayer.order)
    )).scalars().all()

    # Score every player
    breakdown = []
    total_points = 0.0

    for p in players:
        scored = await score_player(p.player_name, entry.match_id, p.role, session)
        breakdown.append(scored)
        total_points += scored["final_points"]

    total_points = round(total_points, 1)

    # Global rank for this match
    other_entries = (await session.execute(
        select(FantasyEntry).where(
            FantasyEntry.match_id == entry.match_id,
            FantasyEntry.status == "REVEALED",
            FantasyEntry.total_points != None,
        )
    )).scalars().all()

    rank = sum(1 for e in other_entries if (e.total_points or 0) > total_points) + 1

    # Update other entries' ranks
    for e in other_entries:
        if (e.total_points or 0) < total_points:
            e.rank_global = (e.rank_global or 1) + 1

    # Save
    entry.status = "REVEALED"
    entry.total_points = total_points
    entry.rank_global = rank
    entry.breakdown = breakdown

    await session.commit()

    # Pretty summary
    pretty = []
    for b in breakdown:
        if b["role"] == "CAPTAIN":
            pretty.append(f"⭐ Captain: {b['player']} → {b['base_points']} pts ×2 = {b['final_points']} pts")
        elif b["role"] == "VICE_CAPTAIN":
            pretty.append(f"�� Vice Captain: {b['player']} → {b['base_points']} pts ×1.5 = {b['final_points']} pts")
        else:
            pretty.append(f"   {b['player']} → {b['final_points']} pts")
    pretty.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━")
    pretty.append(f"TOTAL: {total_points} Fantasy Points | Rank #{rank}")

    return {
        "entry_id": entry.id,
        "match": f"{match.team1} vs {match.team2} ({match.match_date})",
        "actual_winner": match.winner,
        "fantasy_team": team.team_name if team else None,
        "status": "REVEALED",
        "total_points": total_points,
        "rank_global": rank,
        "breakdown": breakdown,
        "pretty_summary": pretty,
    }


@router.get("/leaderboard")
async def fantasy_leaderboard(
    match_id: Optional[int] = Query(None, description="Leaderboard for a specific match"),
    year: Optional[str] = Query(None, description="Best scores for a tournament year"),
    limit: int = Query(10),
    session: AsyncSession = Depends(get_session),
):
    """Global fantasy leaderboard — by match or by year"""
    query = select(FantasyEntry).where(FantasyEntry.status == "REVEALED")
    if match_id:
        query = query.where(FantasyEntry.match_id == match_id)

    entries = (await session.execute(
        query.order_by(FantasyEntry.total_points.desc()).limit(limit)
    )).scalars().all()

    board = []
    for i, e in enumerate(entries):
        user = await session.get(User, e.user_id)
        match = await session.get(Match, e.match_id)
        team = await session.get(FantasyTeam, e.fantasy_team_id)

        if year and match and match.tournament_year != year:
            continue

        board.append({
            "rank": i + 1,
            "username": user.username if user else "Unknown",
            "fantasy_team": team.team_name if team else None,
            "match": f"{match.team1} vs {match.team2}" if match else None,
            "tournament_year": match.tournament_year if match else None,
            "total_points": e.total_points,
        })

    return {
        "filter": {"match_id": match_id, "year": year},
        "leaderboard": board,
    }

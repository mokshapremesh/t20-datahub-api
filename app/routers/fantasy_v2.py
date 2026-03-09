from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime, timezone

from app.db.session import get_session
from app.models.fantasy import FantasyTeam, FantasyTeamPlayer, FantasyEntry
from app.models.match import Match
from app.models.delivery import Delivery
from app.models.user import User
from app.services.auth import get_current_user
from app.schemas.fantasy import (
    FantasyTeamCreate, CaptainBody, FantasyTeamOut, FantasyTeamListOut,
    LeaderboardOut, LeaderboardEntry, SquadOut, SquadPlayer, TeamRequirements
)

NON_BOWLER_WICKETS = {
    "run out", "retired hurt", "retired out", "obstructing the field",
    "hit the ball twice", "handled the ball", "timed out"
}

teams_router = APIRouter(tags=["Fantasy Teams"])
lb_router    = APIRouter(tags=["Fantasy Leaderboards"])
squad_router = APIRouter(tags=["Match Squads"])


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _load_team_owned(team_id: int, user_id: int, session: AsyncSession):
    team = (await session.execute(
        select(FantasyTeam)
        .options(selectinload(FantasyTeam.players), selectinload(FantasyTeam.entries))
        .where(FantasyTeam.id == team_id, FantasyTeam.user_id == user_id)
    )).scalar_one_or_none()
    return team

async def _load_team(team_id: int, session: AsyncSession) -> FantasyTeam:
    team = (await session.execute(
        select(FantasyTeam)
        .options(selectinload(FantasyTeam.players), selectinload(FantasyTeam.entries))
        .where(FantasyTeam.id == team_id)
    )).scalar_one_or_none()
    return team

def _is_locked(team: FantasyTeam) -> bool:
    try:
        entries = list(team.entries) if team.entries is not None else []
        return any(e.status in ("SUBMITTED", "REVEALED") for e in entries)
    except Exception:
        return False

async def _to_out(team: FantasyTeam, locked: bool, session: AsyncSession) -> FantasyTeamOut:
    # Reload with relationships eagerly
    loaded = (await session.execute(
        select(FantasyTeam)
        .options(selectinload(FantasyTeam.players), selectinload(FantasyTeam.entries))
        .where(FantasyTeam.id == team.id)
    )).scalar_one()
    players = [p.player_name for p in sorted(loaded.players, key=lambda x: x.order)]
    captain = next((p.player_name for p in loaded.players if p.role == "CAPTAIN"), None)
    vc      = next((p.player_name for p in loaded.players if p.role == "VICE_CAPTAIN"), None)
    entry   = next((e for e in loaded.entries if e.status in ("SUBMITTED", "REVEALED")), None)
    return FantasyTeamOut(
        id=loaded.id, match_id=loaded.match_id, name=loaded.team_name,
        player_keys=players, captain_key=captain, vice_captain_key=vc,
        status="SUBMITTED" if locked else "DRAFT",
        locked_at=entry.created_at if entry else None,
        total_points=entry.total_points if entry else None,
        requirements=TeamRequirements(required_players=11, current_players=len(players)),
        created_at=loaded.created_at, updated_at=loaded.updated_at,
    )

async def _valid_players(match_id: int, session: AsyncSession) -> set:
    b = set((await session.execute(select(Delivery.batter).where(Delivery.match_id == match_id).distinct())).scalars().all())
    w = set((await session.execute(select(Delivery.bowler).where(Delivery.match_id == match_id).distinct())).scalars().all())
    return b | w


# ── Scoring ───────────────────────────────────────────────────────────────────

async def score_player(player_name: str, match_id: int, role: str, session: AsyncSession) -> dict:
    bat = (await session.execute(select(
        func.sum(Delivery.runs_batter).label("runs"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
        func.count(Delivery.id).filter(Delivery.is_wicket == True).label("dismissed"),
    ).where(Delivery.match_id == match_id, Delivery.batter == player_name))).first()

    runs = bat.runs or 0; fours = bat.fours or 0; sixes = bat.sixes or 0
    dismissed = (bat.dismissed or 0) > 0; balls_faced = bat.balls or 0
    bat_pts = runs + fours + sixes * 2
    if runs >= 50: bat_pts += 20
    elif runs >= 30: bat_pts += 10
    if runs == 0 and dismissed: bat_pts -= 5

    bowl = (await session.execute(select(
        func.count(Delivery.id).filter(
            Delivery.is_wicket == True, Delivery.wicket_type.isnot(None),
            ~func.lower(Delivery.wicket_type).in_(NON_BOWLER_WICKETS)
        ).label("wickets"),
        func.sum(Delivery.runs_total).label("runs_conceded"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls_bowled"),
    ).where(Delivery.match_id == match_id, Delivery.bowler == player_name))).first()

    wickets = bowl.wickets or 0; runs_conceded = bowl.runs_conceded or 0
    balls_bowled = bowl.balls_bowled or 0
    economy = round(runs_conceded / balls_bowled * 6, 2) if balls_bowled > 0 else 0.0
    bowl_pts = wickets * 25
    if wickets >= 4: bowl_pts += 20
    elif wickets >= 3: bowl_pts += 10
    if balls_bowled >= 6:
        if economy < 6: bowl_pts += 6
        elif economy < 7: bowl_pts += 4
        elif economy < 8: bowl_pts += 2
        elif economy >= 10: bowl_pts -= 4
        elif economy >= 9:  bowl_pts -= 2

    base = bat_pts + bowl_pts
    mult = 2.0 if role == "CAPTAIN" else 1.5 if role == "VICE_CAPTAIN" else 1.0
    return {
        "player": player_name, "role": role,
        "batting": {"runs": runs, "balls": balls_faced, "fours": fours, "sixes": sixes, "points": bat_pts},
        "bowling": {"wickets": wickets, "economy": economy, "points": bowl_pts},
        "base_points": base, "multiplier": mult, "final_points": round(base * mult, 1),
    }


# ── Squads ────────────────────────────────────────────────────────────────────

@squad_router.get("/matches/{match_id}/squads", response_model=SquadOut)
async def get_squads(match_id: int, session: AsyncSession = Depends(get_session)):
    """Player pool for a match. Use these player_key values when building your XI."""
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    batters = (await session.execute(
        select(Delivery.batter.label("p"), Delivery.batting_team.label("t"))
        .where(Delivery.match_id == match_id).distinct()
    )).all()
    bowlers = (await session.execute(
        select(Delivery.bowler.label("p"), Delivery.bowling_team.label("t"))
        .where(Delivery.match_id == match_id).distinct()
    )).all()

    player_map: dict[str, str] = {}
    for r in bowlers: player_map[str(r.p)] = str(r._t)
    for r in batters:  player_map[str(r.p)] = str(r._t)  # batting_team wins

    by_team: dict[str, list] = {match.team1: [], match.team2: []}
    for pname, pteam in sorted(player_map.items()):
        if pteam not in by_team: by_team[pteam] = []
        by_team[pteam].append(SquadPlayer(player_key=pname, team=pteam))

    return SquadOut(
        match_id=match_id, matchup=f"{match.team1} vs {match.team2}",
        date=str(match.match_date), players=by_team,
        links={
            "my_teams": f"/matches/{match_id}/fantasy/teams",
            "create_team": f"/matches/{match_id}/fantasy/teams",
            "scorecard": f"/matches/{match_id}/scorecard",
        }
    )


# ── Fantasy Teams ─────────────────────────────────────────────────────────────

@teams_router.get("/matches/{match_id}/fantasy/teams", response_model=FantasyTeamListOut)
async def list_teams(
    match_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List my fantasy teams for this match."""
    teams = (await session.execute(
        select(FantasyTeam)
        .options(selectinload(FantasyTeam.players), selectinload(FantasyTeam.entries))
        .where(FantasyTeam.match_id == match_id, FantasyTeam.user_id == current_user.id)
        .order_by(FantasyTeam.created_at.desc()).limit(limit).offset(offset)
    )).scalars().all()
    return FantasyTeamListOut(total=len(teams), returned=len(teams),
                              teams=[await _to_out(t, _is_locked(t), session) for t in teams])


@teams_router.post("/matches/{match_id}/fantasy/teams", response_model=FantasyTeamOut, status_code=201)
async def create_team(
    match_id: int,
    name: str = Query(..., description="Team name e.g. My Dream XI"),
    player_keys: list[str] = Query(default=[], description="Player keys from GET /matches/{match_id}/squads — add up to 11"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create a draft fantasy team. Optionally include up to 11 player_keys,
    captain_key and vice_captain_key. All player_keys must come from GET /matches/{match_id}/squads.
    """
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if player_keys:
        if len(set(player_keys)) != len(player_keys):
            raise HTTPException(status_code=400, detail="Duplicate player_keys.")
        if len(player_keys) > 11:
            raise HTTPException(status_code=400, detail="Maximum 11 players.")
        valid = await _valid_players(match_id, session)
        invalid = [p for p in player_keys if p not in valid]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid players: {invalid}. Use GET /matches/{match_id}/squads")
        if None and None not in player_keys:
            raise HTTPException(status_code=400, detail="captain_key must be in player_keys.")
        if None and None not in player_keys:
            raise HTTPException(status_code=400, detail="vice_captain_key must be in player_keys.")
        if None and None and None == None:
            raise HTTPException(status_code=409, detail="captain_key and vice_captain_key must differ.")

    team = FantasyTeam(user_id=current_user.id, match_id=match_id, team_name=name)
    session.add(team)
    await session.flush()

    for i, pk in enumerate(player_keys):
        role = "CAPTAIN" if pk == None else "VICE_CAPTAIN" if pk == None else "PLAYER"
        session.add(FantasyTeamPlayer(
            fantasy_team_id=team.id, player_name=pk,
            tournament_year=match.tournament_year or "", role=role, order=i
        ))

    await session.commit()
    await session.refresh(team)
    return await _to_out(team, False, session)


@teams_router.put("/fantasy/teams/{team_id}/captain", response_model=FantasyTeamOut)
async def set_captain(
    team_id: int,
    player_key: str = Query(..., description="Player key from your team e.g. V Kohli"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Set captain (2× points). Player must already be in your team."""
    team = (await _load_team_owned(team_id, current_user.id, session))
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    if _is_locked(team): raise HTTPException(status_code=409, detail="Team is locked.")
    player = next((p for p in team.players if p.player_name == player_key), None)
    if not player: raise HTTPException(status_code=404, detail=f"'{player_key}' not in team.")
    vc = next((p for p in team.players if p.role == "VICE_CAPTAIN"), None)
    if vc and vc.player_name == player_key:
        raise HTTPException(status_code=409, detail="Already vice captain.")
    for p in team.players:
        if p.role == "CAPTAIN": p.role = "PLAYER"
    player.role = "CAPTAIN"
    await session.commit()
    await session.refresh(team)
    return await _to_out(team, False, session)


@teams_router.put("/fantasy/teams/{team_id}/vice-captain", response_model=FantasyTeamOut)
async def set_vice_captain(
    team_id: int,
    player_key: str = Query(..., description="Player key from your team e.g. RG Sharma"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Set vice captain (1.5× points). Player must already be in your team."""
    team = (await _load_team_owned(team_id, current_user.id, session))
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    if _is_locked(team): raise HTTPException(status_code=409, detail="Team is locked.")
    player = next((p for p in team.players if p.player_name == player_key), None)
    if not player: raise HTTPException(status_code=404, detail=f"'{player_key}' not in team.")
    cap = next((p for p in team.players if p.role == "CAPTAIN"), None)
    if cap and cap.player_name == player_key:
        raise HTTPException(status_code=409, detail="Already captain.")
    for p in team.players:
        if p.role == "VICE_CAPTAIN": p.role = "PLAYER"
    player.role = "VICE_CAPTAIN"
    await session.commit()
    await session.refresh(team)
    return await _to_out(team, False, session)


@teams_router.get("/fantasy/teams/{team_id}", response_model=FantasyTeamOut)
async def get_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get your fantasy team."""
    team = (await _load_team_owned(team_id, current_user.id, session))
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    return await _to_out(team, _is_locked(team, session))


@teams_router.delete("/fantasy/teams/{team_id}", status_code=204)
async def delete_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a draft team."""
    team = (await _load_team_owned(team_id, current_user.id, session))
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    if _is_locked(team): raise HTTPException(status_code=409, detail="Cannot delete a submitted team.")
    await session.delete(team)
    await session.commit()


@teams_router.post("/fantasy/teams/{team_id}/submit", response_model=FantasyTeamOut)
async def submit_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Lock your team — DRAFT → SUBMITTED. Requires 11 players, captain and vice captain."""
    team = (await _load_team_owned(team_id, current_user.id, session))
    if not team: raise HTTPException(status_code=404, detail="Team not found")
    if _is_locked(team): raise HTTPException(status_code=409, detail="Already submitted.")
    if len(team.players) != 11:
        raise HTTPException(status_code=400, detail=f"Need 11 players — have {len(team.players)}")
    if not any(p.role == "CAPTAIN" for p in team.players):
        raise HTTPException(status_code=400, detail="No captain set.")
    if not any(p.role == "VICE_CAPTAIN" for p in team.players):
        raise HTTPException(status_code=400, detail="No vice captain set.")

    breakdown = []; total = 0.0
    for p in team.players:
        scored = await score_player(p.player_name, team.match_id, p.role, session)
        breakdown.append(scored); total += scored["final_points"]
    total = round(total, 1)

    others = (await session.execute(
        select(FantasyEntry).where(FantasyEntry.match_id == team.match_id, FantasyEntry.status == "SUBMITTED")
    )).scalars().all()
    rank = sum(1 for e in others if (e.total_points or 0) > total) + 1

    session.add(FantasyEntry(
        user_id=current_user.id, match_id=team.match_id, fantasy_team_id=team.id,
        status="SUBMITTED", total_points=total, rank_global=rank, breakdown=breakdown
    ))
    await session.commit()
    await session.refresh(team)
    return await _to_out(team, True, session)


# ── Leaderboards ──────────────────────────────────────────────────────────────

@lb_router.get("/matches/{match_id}/fantasy/leaderboard", response_model=LeaderboardOut)
async def match_leaderboard(
    match_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Ranked leaderboard of submitted teams for a match."""
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    entries = (await session.execute(
        select(FantasyEntry)
        .where(FantasyEntry.match_id == match_id, FantasyEntry.status == "SUBMITTED")
        .order_by(FantasyEntry.total_points.desc())
    )).scalars().all()
    board = []
    for i, e in enumerate(entries):
        user = await session.get(User, e.user_id)
        ft   = await session.get(FantasyTeam, e.fantasy_team_id)
        board.append(LeaderboardEntry(rank=i+1, username=user.username if user else "?",
                                      team_name=ft.team_name if ft else "—", total_points=e.total_points, breakdown=e.breakdown))
    return LeaderboardOut(match_id=match_id, year=match.tournament_year, total=len(board), returned=len(board), leaderboard=board)


@lb_router.get("/fantasy/leaderboard", response_model=LeaderboardOut)
async def global_leaderboard(
    year:   Optional[str] = Query(None, description="Tournament year e.g. 2024"),
    session: AsyncSession = Depends(get_session),
):
    """Global leaderboard across all matches."""
    q = select(FantasyEntry).where(FantasyEntry.status == "SUBMITTED")
    if year:
        mids = (await session.execute(select(Match.id).where(Match.tournament_year == year))).scalars().all()
        q = q.where(FantasyEntry.match_id.in_(mids))
    entries = (await session.execute(q.order_by(FantasyEntry.total_points.desc()))).scalars().all()
    board = []
    for i, e in enumerate(entries):
        user = await session.get(User, e.user_id)
        ft   = await session.get(FantasyTeam, e.fantasy_team_id)
        board.append(LeaderboardEntry(rank=i+1, username=user.username if user else "?",
                                      team_name=ft.team_name if ft else "—", total_points=e.total_points))
    return LeaderboardOut(year=year, total=len(board), returned=len(board), leaderboard=board)

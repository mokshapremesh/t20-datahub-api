from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, or_
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

# ── Constants ─────────────────────────────────────────────────────────────────

NON_BOWLER_WICKETS = {
    "run out", "retired hurt", "retired out", "obstructing the field",
    "hit the ball twice", "handled the ball", "timed out"
}

def bowler_wicket_filter():
    """Excludes NULLs, run-outs, and non-bowler dismissals. Case-insensitive."""
    return (
        Delivery.is_wicket == True,
        Delivery.wicket_type.isnot(None),
        ~func.lower(Delivery.wicket_type).in_(NON_BOWLER_WICKETS),
    )

# ── Pydantic models ───────────────────────────────────────────────────────────

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

# ── Helpers ───────────────────────────────────────────────────────────────────

async def validate_team(team: str, session: AsyncSession):
    exists = (await session.execute(
        select(Match.team1).where(or_(Match.team1 == team, Match.team2 == team)).limit(1)
    )).scalar()
    if not exists:
        raise HTTPException(status_code=400, detail=f"'{team}' not found. Use GET /options/teams")

async def resolve_player(player_key: str, session: AsyncSession) -> str | None:
    """Exact match only — canonical key must come from GET /options/players."""
    exact = (await session.execute(
        select(Delivery.batter).where(Delivery.batter == player_key).limit(1)
    )).scalar()
    if exact:
        return exact
    return (await session.execute(
        select(Delivery.bowler).where(Delivery.bowler == player_key).limit(1)
    )).scalar()

async def validate_player(player_key: str, session: AsyncSession):
    if not await resolve_player(player_key, session):
        raise HTTPException(status_code=400, detail=f"'{player_key}' not found. Use GET /options/players to get the exact key.")

def _profile_dict(p: FanProfile) -> dict:
    return {
        "display_name": p.display_name,
        "fav_team":   {"key": p.fav_team, "name": p.fav_team},
        "fav_player": {"key": p.fav_player_key, "name": p.fav_player_key.replace("_", " ") if p.fav_player_key else None},
        "fav_year":   p.fav_year,
        "created_at": str(p.created_at),
        "updated_at": str(p.updated_at),
    }

# ── Profile CRUD ──────────────────────────────────────────────────────────────

@router.post("/profile", status_code=201, include_in_schema=False)
async def create_profile(
    response: Response,
    display_name:   Optional[str] = Query(None, description="Your display name"),
    fav_team:       Optional[str] = Query(None, description="Favourite team e.g. India"),
    fav_player_key: Optional[str] = Query(None, description="Favourite player key e.g. V Kohli"),
    fav_year:       Optional[str] = Query(None, description="Favourite tournament year e.g. 2024"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create profile — fails if already exists. Use PUT to upsert."""
    existing = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Profile exists. Use PUT /me/profile to replace.")
    if fav_team:       await validate_team(fav_team, session)
    if fav_player_key: await validate_player(fav_player_key, session)
    profile = FanProfile(user_id=current_user.id, display_name=display_name, fav_team=fav_team, fav_player_key=fav_player_key, fav_year=fav_year)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    response.headers["Location"] = "/me/profile"
    return {"message": "Profile created", "profile": _profile_dict(profile), "links": {"self": "/me/profile", "dashboard": "/me/dashboard"}}

@router.put("/profile")
async def upsert_profile(
    display_name:   Optional[str] = Query(None, description="Your display name"),
    fav_team:       Optional[str] = Query(None, description="Favourite team e.g. India"),
    fav_player_key: Optional[str] = Query(None, description="Favourite player key e.g. V Kohli"),
    fav_year:       Optional[str] = Query(None, description="Favourite tournament year e.g. 2024"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upsert — creates if not exists (201), replaces if exists (200)."""
    if fav_team:       await validate_team(fav_team, session)
    if fav_player_key: await validate_player(fav_player_key, session)
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    created = profile is None
    if created:
        profile = FanProfile(user_id=current_user.id)
        session.add(profile)
    profile.display_name   = display_name
    profile.fav_team       = fav_team
    profile.fav_player_key = fav_player_key
    profile.fav_year       = fav_year
    await session.commit()
    await session.refresh(profile)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=201 if created else 200,
        content={"message": "Profile created" if created else "Profile updated", "profile": _profile_dict(profile), "links": {"self": "/me/profile", "dashboard": "/me/dashboard"}}
    )

@router.patch("/profile", status_code=200, include_in_schema=False)
async def patch_profile(
    display_name:   Optional[str] = Query(None, description="Update display name"),
    fav_team:       Optional[str] = Query(None, description="Update favourite team"),
    fav_player_key: Optional[str] = Query(None, description="Update favourite player key"),
    fav_year:       Optional[str] = Query(None, description="Update favourite year"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Partial update — only provided fields are changed."""
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Use PUT /me/profile first.")
    if fav_team       is not None: await validate_team(fav_team, session);         profile.fav_team       = fav_team
    if fav_player_key is not None: await validate_player(fav_player_key, session); profile.fav_player_key = fav_player_key
    if display_name   is not None: profile.display_name = display_name
    if fav_year       is not None: profile.fav_year     = fav_year
    await session.commit()
    await session.refresh(profile)
    return {"message": "Profile updated", "profile": _profile_dict(profile), "links": {"self": "/me/profile", "dashboard": "/me/dashboard"}}

@router.get("/profile")
async def get_profile(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Get stored profile preferences."""
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        return {"message": "No profile yet.", "links": {"create": "PUT /me/profile", "teams": "/options/teams", "players": "/options/players"}}
    return {**_profile_dict(profile), "links": {"self": "/me/profile", "dashboard": "/me/dashboard"}}

@router.delete("/profile", status_code=204)
async def delete_profile(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Delete profile — 204 No Content."""
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found.")
    await session.delete(profile)
    await session.commit()

# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """
    Personalised dashboard scoped to fav_year.
    - Team: win/loss/no_result, stage breakdown, batting/bowling averages, year_by_year
    - Player: tournament stats (scoped to fav_year) + full career WC history (all years)
    - Bowling wickets exclude run-outs and NULL wicket_type rows
    """
    profile = (await session.execute(select(FanProfile).where(FanProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found. Use PUT /me/profile first.")

    result = {
        "profile":           _profile_dict(profile),
        "scope":             {"competition": "T20 World Cup", "year": profile.fav_year},
        "dashboard_version": "v1",
        "dataset":           "cricsheet_t20s_male_json",
        "dashboard":         {},
        "generated_at":      datetime.utcnow().isoformat() + "Z",
        "links":             {"profile": "/me/profile", "teams": "/options/teams", "players": "/options/players"}
    }

    # ── Team block ────────────────────────────────────────────────────────────
    if profile.fav_team:
        q = select(Match).where(or_(Match.team1 == profile.fav_team, Match.team2 == profile.fav_team))
        if profile.fav_year:
            q = q.where(Match.tournament_year == profile.fav_year)
        matches    = (await session.execute(q)).scalars().all()
        wins       = sum(1 for m in matches if m.winner == profile.fav_team)
        losses     = sum(1 for m in matches if m.winner is not None and m.winner != profile.fav_team)
        no_results = sum(1 for m in matches if m.winner is None)
        n          = max(len(matches), 1)

        stage_dist = {}
        for m in matches:
            s = m.stage or "Group"
            stage_dist[s] = stage_dist.get(s, 0) + 1

        year_record = {}
        for m in matches:
            y = m.tournament_year or "unknown"
            if y not in year_record:
                year_record[y] = {"matches": 0, "wins": 0, "losses": 0, "no_results": 0}
            year_record[y]["matches"] += 1
            if m.winner == profile.fav_team:                        year_record[y]["wins"]       += 1
            elif m.winner is None:                                   year_record[y]["no_results"] += 1
            else:                                                    year_record[y]["losses"]     += 1

        match_ids = [m.id for m in matches]
        if match_ids:
            bat   = (await session.execute(select(func.sum(Delivery.runs_total).label("runs")).where(Delivery.match_id.in_(match_ids), Delivery.batting_team == profile.fav_team))).first()
            bowl  = (await session.execute(select(func.sum(Delivery.runs_total).label("runs")).where(Delivery.match_id.in_(match_ids), Delivery.bowling_team == profile.fav_team))).first()
            death = (await session.execute(select(func.sum(Delivery.runs_total).label("runs"), func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls")).where(Delivery.match_id.in_(match_ids), Delivery.bowling_team == profile.fav_team, Delivery.over >= 16))).first()
            bat_runs    = bat.runs   or 0
            bowl_runs   = bowl.runs  or 0
            death_runs  = death.runs or 0
            death_balls = death.balls or 1
        else:
            bat_runs = bowl_runs = death_runs = 0
            death_balls = 1

        result["dashboard"]["team"] = {
            "name":    profile.fav_team,
            "summary": {
                "matches":    len(matches),
                "wins":       wins,
                "losses":     losses,
                "no_results": no_results,
                "win_rate":   round(wins / max(wins + losses, 1) * 100, 1)
            },
            "stage_distribution": stage_dist,
            "year_by_year": {y: v for y, v in sorted(year_record.items())},
            "batting": {"avg_runs_scored_per_match":  round(bat_runs  / n, 1)},
            "bowling": {"avg_runs_conceded_per_match": round(bowl_runs / n, 1),
                        "death_overs_economy":         round(death_runs / death_balls * 6, 2)}
        }
        result["links"]["team_matches"] = f"/matches?team={profile.fav_team}&year={profile.fav_year}"

    # ── Player block ──────────────────────────────────────────────────────────
    if profile.fav_player_key:
        resolved = await resolve_player(profile.fav_player_key, session)

        if resolved:
            # Scoped match IDs for tournament stats
            scoped_mids = None
            if profile.fav_year:
                scoped_mids = (await session.execute(
                    select(Match.id).where(Match.tournament_year == profile.fav_year)
                )).scalars().all()

            def scoped(q):
                return q.where(Delivery.match_id.in_(scoped_mids)) if scoped_mids else q

            # Tournament batting stats (scoped)
            bat = (await session.execute(scoped(select(
                func.sum(Delivery.runs_batter).label("runs"),
                func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
                func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
                func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes")
            ).where(Delivery.batter == resolved)))).first()

            # Tournament bowling stats (scoped)
            bowl = (await session.execute(scoped(select(
                func.count(Delivery.id).filter(*bowler_wicket_filter()).label("wickets"),
                func.sum(Delivery.runs_total).label("runs_conceded"),
                func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls")
            ).where(Delivery.bowler == resolved)))).first()

            runs  = bat.runs  or 0
            balls = bat.balls or 1

            # Best match (scoped)
            best_bat = (await session.execute(scoped(
                select(Delivery.match_id, func.sum(Delivery.runs_batter).label("runs"))
                .where(Delivery.batter == resolved)
                .group_by(Delivery.match_id)
                .order_by(func.sum(Delivery.runs_batter).desc())
                .limit(1)
            ))).first()

            best_match = None
            if best_bat:
                m = await session.get(Match, best_bat.match_id)
                if m:
                    best_match = {"match_id": best_bat.match_id, "label": f"{m.team1} vs {m.team2} ({m.match_date})", "runs": best_bat.runs}

            # Career WC history — all years, single query with filtered aggregates
            # runs only counted on rows where player is batter
            # wickets only counted on rows where player is bowler
            yr_rows = (await session.execute(
                select(
                    Match.tournament_year.label("year"),
                    func.count(distinct(Delivery.match_id)).label("matches"),
                    func.sum(Delivery.runs_batter).filter(Delivery.batter == resolved).label("runs"),
                    func.count(Delivery.id).filter(
                        Delivery.bowler == resolved,
                        *bowler_wicket_filter()
                    ).label("wickets"),
                )
                .join(Match, Delivery.match_id == Match.id)
                .where(or_(Delivery.batter == resolved, Delivery.bowler == resolved))
                .group_by(Match.tournament_year)
                .order_by(Match.tournament_year)
            )).all()

            career_history = {
                r.year: {
                    "matches":  r.matches,
                    "runs":     int(r.runs    or 0),
                    "wickets":  int(r.wickets or 0),
                }
                for r in yr_rows
            }

            result["dashboard"]["player"] = {
                "name": resolved,
                "tournament": {
                    "year":    profile.fav_year,
                    "batting": {
                        "runs":         runs,
                        "balls":        bat.balls or 0,
                        "strike_rate":  round(runs / balls * 100, 1),
                        "fours":        bat.fours or 0,
                        "sixes":        bat.sixes or 0
                    },
                    "bowling": {
                        "wickets": bowl.wickets or 0,
                        "economy": round((bowl.runs_conceded or 0) / max(bowl.balls or 1, 1) * 6, 2)
                    },
                    "best_match": best_match
                },
                "career_wc_history": career_history
            }
            result["links"]["player_stats"] = f"/analytics/player/{resolved.replace(' ', '_')}?year={profile.fav_year}"

    return result


# ── Options ───────────────────────────────────────────────────────────────────

options_router = APIRouter(prefix="/options", tags=["Options & Dropdowns"])

@options_router.get("/teams")
async def get_teams(year: Optional[str] = Query(None), session: AsyncSession = Depends(get_session)):
    """
    All teams with win/loss/no-result counts. Supports ?year= to match dashboard scope.
    Note: aggregates computed on demand; in production these would be cached or materialized.
    """
    q1 = select(Match.team1.label("team"), Match.winner)
    q2 = select(Match.team2.label("team"), Match.winner)
    if year:
        q1 = q1.where(Match.tournament_year == year)
        q2 = q2.where(Match.tournament_year == year)
    rows = list((await session.execute(q1)).all()) + list((await session.execute(q2)).all())

    team_stats: dict[str, dict] = {}
    for team, winner in rows:
        if team not in team_stats:
            team_stats[team] = {"matches": 0, "wins": 0, "losses": 0, "no_results": 0}
        team_stats[team]["matches"] += 1
        if winner == team:   team_stats[team]["wins"]       += 1
        elif winner is None: team_stats[team]["no_results"] += 1
        else:                team_stats[team]["losses"]     += 1

    teams = sorted([
        {"team_key": t, "name": t, **s,
         "win_rate": round(s["wins"] / max(s["wins"] + s["losses"], 1) * 100, 1)}
        for t, s in team_stats.items()
    ], key=lambda x: x["matches"], reverse=True)
    return {"total": len(teams), "filter": {"year": year}, "teams": teams}

@options_router.get("/players")
async def get_players(
    team:    Optional[str] = Query(None),
    year:    Optional[str] = Query(None),
    search:  Optional[str] = Query(None, description="Fuzzy name search"),
    limit:   int           = Query(200, ge=1, le=500),
    offset:  int           = Query(0,   ge=0),
    session: AsyncSession  = Depends(get_session)
):
    """
    Players with stats. Use exact player_key value for fav_player_key in your profile.
    Supports ?team=, ?year=, ?search=, ?limit=, ?offset=
    """
    match_q = select(Match.id)
    if year: match_q = match_q.where(Match.tournament_year == year)
    if team: match_q = match_q.where(or_(Match.team1 == team, Match.team2 == team))
    match_ids = (await session.execute(match_q)).scalars().all()
    if not match_ids:
        raise HTTPException(status_code=404, detail="No matches found for given filters.")

    bat_q = select(
        Delivery.batter.label("player"),
        Delivery.batting_team.label("team"),
        func.sum(Delivery.runs_batter).label("runs"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes")
    ).where(Delivery.match_id.in_(match_ids)).group_by(Delivery.batter, Delivery.batting_team)

    bowl_q = select(
        Delivery.bowler.label("player"),
        Delivery.bowling_team.label("team"),
        func.count(Delivery.id).filter(*bowler_wicket_filter()).label("wickets"),
        func.sum(Delivery.runs_total).label("runs_conceded"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls")
    ).where(Delivery.match_id.in_(match_ids)).group_by(Delivery.bowler, Delivery.bowling_team)
    if team:
        bat_q  = bat_q.where(Delivery.batting_team == team)
        bowl_q = bowl_q.where(Delivery.bowling_team == team)

    if search:
        bat_q  = bat_q.where(Delivery.batter.ilike(f"%{search}%"))
        bowl_q = bowl_q.where(Delivery.bowler.ilike(f"%{search}%"))

    batters = (await session.execute(bat_q)).all()
    bowlers = (await session.execute(bowl_q)).all()

    player_map: dict[str, dict] = {}
    for b in batters:
        runs = b.runs or 0; balls = b.balls or 1
        player_map[b.player] = {"player_key": b.player, "name": b.player, "team": b.team, "runs": runs, "strike_rate": round(runs / balls * 100, 1), "fours": b.fours or 0, "sixes": b.sixes or 0, "wickets": 0, "economy": 0.0}
    for b in bowlers:
        balls = b.balls or 1; economy = round((b.runs_conceded or 0) / balls * 6, 2)
        if b.player in player_map:
            player_map[b.player]["wickets"] = b.wickets or 0
            player_map[b.player]["economy"] = economy
            if not player_map[b.player]["team"]: player_map[b.player]["team"] = b.team
        else:
            player_map[b.player] = {"player_key": b.player, "name": b.player, "team": b.team, "runs": 0, "strike_rate": 0.0, "fours": 0, "sixes": 0, "wickets": b.wickets or 0, "economy": economy}

    players   = sorted(player_map.values(), key=lambda x: x["runs"] + x["wickets"] * 25, reverse=True)
    paginated = players[offset: offset + limit]
    return {
        "total":    len(players),
        "returned": len(paginated),
        "offset":   offset,
        "limit":    limit,
        "filters":  {"team": team, "year": year, "search": search},
        "note":     "Use player_key exactly as shown when setting fav_player_key in your profile.",
        "players":  paginated
    }

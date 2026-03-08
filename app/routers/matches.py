from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime
from app.db.session import get_session
from app.models.match import Match
from app.models.delivery import Delivery
from app.models.user import User
from app.services.auth import get_current_user, get_admin_user
from app.schemas.matches import MatchOut, MatchListOut, MatchFilters, MatchCreate, MatchUpdate
from app.schemas.scorecard import (
    ScorecardOut, ScorecardMatchHeader, InningsCard, InningsSummary,
    BattingRow, BowlingRow, ExtrasBreakdown, FallOfWicket, OverSummary
)

router = APIRouter(prefix="/matches", tags=["Matches"])
admin_router = APIRouter(prefix="/matches", tags=["Admin - Matches"])


# ── List Matches ──────────────────────────────────────────────────────────────

@router.get("", response_model=MatchListOut)
async def list_matches(
    team:   Optional[str] = Query(None, description="Filter by team name"),
    year:   Optional[str] = Query(None, description="Tournament year e.g. 2024", pattern=r"^\d{4}$"),
    stage:  Optional[str] = Query(None, description="e.g. Final, Semi Final, Group"),
    venue:  Optional[str] = Query(None, description="Venue name (partial match)"),
    session: AsyncSession = Depends(get_session),
):
    """List matches with optional filters and pagination."""
    query = select(Match)
    if team:  query = query.where((Match.team1.ilike(f"%{team}%")) | (Match.team2.ilike(f"%{team}%")))
    if year:  query = query.where(Match.tournament_year == year)
    if stage: query = query.where(Match.stage.ilike(f"%{stage}%"))
    if venue: query = query.where(Match.venue.ilike(f"%{venue}%"))

    total_q = query
    matches = (await session.execute(
        query.order_by(Match.match_date.desc())
    )).scalars().all()

    returned = len(matches)

    return MatchListOut(
        total=returned,
        returned=returned,
        filters=MatchFilters(team=team, year=year, stage=stage, venue=venue),
        matches=[MatchOut.model_validate(m) for m in matches],
    )


# ── Get Match ─────────────────────────────────────────────────────────────────

@router.get("/{match_id}", response_model=MatchOut)
async def get_match(match_id: int, session: AsyncSession = Depends(get_session)):
    """Get a single match by ID."""
    match = (await session.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchOut.model_validate(match)


# ── Scorecard ─────────────────────────────────────────────────────────────────

@router.get("/{match_id}/scorecard", response_model=ScorecardOut, tags=["Matches"])
async def get_scorecard(
    match_id: int,
    include: Optional[str] = Query(None, description="Comma-separated extras: overs,fow"),
    innings: Optional[int] = Query(None, description="Return single innings only (1 or 2)"),
    session: AsyncSession = Depends(get_session),
):
    """
    Full ball-by-ball scorecard for a match.
    - `include=overs` adds over-by-over breakdown
    - `include=fow` adds fall of wickets
    - `innings=1` or `innings=2` returns a single innings block
    """
    match = (await session.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    include_flags = set(include.split(",")) if include else set()

    all_deliveries = (await session.execute(
        select(Delivery)
        .where(Delivery.match_id == match_id)
        .order_by(Delivery.innings_number, Delivery.over, Delivery.ball_in_over)
    )).scalars().all()

    # Group by innings
    innings_map: dict[int, list] = {}
    for d in all_deliveries:
        innings_map.setdefault(d.innings_number, []).append(d)

    innings_cards = []
    for inn_no, deliveries in sorted(innings_map.items()):
        if innings is not None and inn_no != innings:
            continue

        batting_team  = deliveries[0].batting_team
        bowling_team  = deliveries[0].bowling_team

        # ── Batting ──────────────────────────────────────────────────────────
        batter_map: dict[str, dict] = {}
        wicket_sequence = []
        for d in deliveries:
            b = d.batter
            if b not in batter_map:
                batter_map[b] = {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissal": "not out"}
            batter_map[b]["runs"] += d.runs_batter
            if d.is_legal: batter_map[b]["balls"] += 1
            if d.runs_batter == 4: batter_map[b]["fours"] += 1
            if d.runs_batter == 6: batter_map[b]["sixes"] += 1
            if d.is_wicket and d.batter == b:
                wt = d.wicket_type or "out"
                batter_map[b]["dismissal"] = wt
                total_runs = sum(x["runs"] for x in batter_map.values())
                wkt_no = sum(1 for x in batter_map.values() if x["dismissal"] != "not out")
                wicket_sequence.append({
                    "wkt": wkt_no, "score": f"{total_runs}/{wkt_no}",
                    "player": b, "over": f"{d.over}.{d.ball_in_over}"
                })

        batting_rows = [
            BattingRow(
                batter=name,
                dismissal=stats["dismissal"],
                runs=stats["runs"],
                balls=stats["balls"],
                fours=stats["fours"],
                sixes=stats["sixes"],
                strike_rate=round(stats["runs"] / max(stats["balls"], 1) * 100, 1)
            )
            for name, stats in batter_map.items()
        ]

        # ── Bowling ──────────────────────────────────────────────────────────
        bowler_map: dict[str, dict] = {}
        for d in deliveries:
            bw = d.bowler
            if bw not in bowler_map:
                bowler_map[bw] = {"legal": 0, "runs": 0, "wickets": 0, "maidens": 0, "_over_runs": {}}
            if d.is_legal: bowler_map[bw]["legal"] += 1
            bowler_map[bw]["runs"] += d.runs_total
            if d.is_wicket and d.wicket_type not in {
                "run out", "retired hurt", "retired out",
                "obstructing the field", "hit the ball twice",
                "handled the ball", "timed out"
            } and d.wicket_type is not None:
                bowler_map[bw]["wickets"] += 1
            ov = d.over
            bowler_map[bw]["_over_runs"].setdefault(ov, 0)
            bowler_map[bw]["_over_runs"][ov] += d.runs_total

        for bw, stats in bowler_map.items():
            stats["maidens"] = sum(1 for r in stats["_over_runs"].values() if r == 0)

        bowling_rows = [
            BowlingRow(
                bowler=name,
                overs=f"{stats['legal'] // 6}.{stats['legal'] % 6}",
                maidens=stats["maidens"],
                runs=stats["runs"],
                wickets=stats["wickets"],
                economy=round(stats["runs"] / max(stats["legal"] / 6, 0.1), 2)
            )
            for name, stats in bowler_map.items()
        ]

        # ── Extras ───────────────────────────────────────────────────────────
        extras = ExtrasBreakdown(
            total=sum(d.runs_extras for d in deliveries if d.runs_extras),
            wides=sum(d.runs_extras for d in deliveries if not d.is_legal and d.wicket_type is None and d.runs_total > d.runs_batter),
            noballs=sum(1 for d in deliveries if not d.is_legal),
            byes=0, legbyes=0, penalty=0
        )

        # ── Summary ──────────────────────────────────────────────────────────
        total_runs    = sum(d.runs_total for d in deliveries)
        total_wickets = sum(1 for d in deliveries if d.is_wicket)
        legal_balls   = sum(1 for d in deliveries if d.is_legal)
        overs_str     = f"{legal_balls // 6}.{legal_balls % 6}"
        run_rate      = round(total_runs / max(legal_balls / 6, 0.1), 2)

        summary = InningsSummary(runs=total_runs, wkts=total_wickets, overs=overs_str, run_rate=run_rate)

        # ── Fall of Wickets ───────────────────────────────────────────────────
        fow = [FallOfWicket(**w) for w in wicket_sequence] if "fow" in include_flags or True else []

        # ── Over summary (optional) ───────────────────────────────────────────
        over_summaries = None
        if "overs" in include_flags:
            over_map: dict[int, dict] = {}
            for d in deliveries:
                ov = d.over
                over_map.setdefault(ov, {"runs": 0, "wickets": 0, "legal": 0})
                over_map[ov]["runs"] += d.runs_total
                if d.is_wicket: over_map[ov]["wickets"] += 1
                if d.is_legal:  over_map[ov]["legal"] += 1
            over_summaries = [
                OverSummary(over=ov, runs=v["runs"], wickets=v["wickets"], legal_balls=v["legal"])
                for ov, v in sorted(over_map.items())
            ]

        innings_cards.append(InningsCard(
            innings_no=inn_no,
            batting_team=batting_team,
            bowling_team=bowling_team,
            summary=summary,
            batting=batting_rows,
            bowling=bowling_rows,
            extras=extras,
            fall_of_wkts=fow,
            overs=over_summaries,
        ))

    return ScorecardOut(
        match=ScorecardMatchHeader(
            match_id=match.id, team1=match.team1, team2=match.team2,
            match_date=match.match_date, venue=match.venue, stage=match.stage,
            tournament_year=match.tournament_year, winner=match.winner
        ),
        innings=innings_cards,
        generated_at=datetime.utcnow(),
        version="v1"
    )


# ── Admin CUD ─────────────────────────────────────────────────────────────────

@admin_router.post("", status_code=201, response_model=MatchOut)
async def create_match(
    body: MatchCreate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Admin only — create a match."""
    match = Match(**body.model_dump(exclude_none=True))
    session.add(match)
    await session.commit()
    await session.refresh(match)
    return MatchOut.model_validate(match)


@admin_router.patch("/{match_id}", response_model=MatchOut)
async def update_match(
    match_id: int,
    body: MatchUpdate,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Admin only — partial update a match."""
    match = (await session.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(match, field, value)
    await session.commit()
    await session.refresh(match)
    return MatchOut.model_validate(match)


@admin_router.delete("/{match_id}", status_code=204)
async def delete_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_admin_user),
):
    """Admin only — delete a match."""
    match = (await session.execute(select(Match).where(Match.id == match_id))).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    await session.delete(match)
    await session.commit()

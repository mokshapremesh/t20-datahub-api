from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_session
from app.models.fantasy import FantasyTeam, FantasyTeamPlayer
from app.models.delivery import Delivery
from app.models.match import Match
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(prefix="/fantasy", tags=["Fantasy Team"])


async def get_player_stats(player_name: str, year: str, session: AsyncSession) -> dict:

    # Batting stats
    batting_query = select(
        func.sum(Delivery.runs_batter).label("runs"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls"),
        func.count(Delivery.id).filter(Delivery.is_wicket == True).label("dismissals"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 4).label("fours"),
        func.count(Delivery.id).filter(Delivery.runs_batter == 6).label("sixes"),
    ).join(Match, Delivery.match_id == Match.id).where(
        Delivery.batter == player_name
    )
    if year != "all":
        batting_query = batting_query.where(Match.tournament_year == year)

    batting_row = (await session.execute(batting_query)).first()
    runs = batting_row.runs or 0
    balls = batting_row.balls or 0
    fours = batting_row.fours or 0
    sixes = batting_row.sixes or 0
    dismissals = batting_row.dismissals or 0
    strike_rate = round((runs / balls * 100), 2) if balls > 0 else 0
    average = round(runs / dismissals, 2) if dismissals > 0 else runs

    # Bowling stats
    bowling_query = select(
        func.count(Delivery.id).filter(Delivery.is_wicket == True).label("wickets"),
        func.sum(Delivery.runs_total).label("runs_conceded"),
        func.count(Delivery.id).filter(Delivery.is_legal == True).label("balls_bowled"),
    ).join(Match, Delivery.match_id == Match.id).where(
        Delivery.bowler == player_name
    )
    if year != "all":
        bowling_query = bowling_query.where(Match.tournament_year == year)

    bowling_row = (await session.execute(bowling_query)).first()
    wickets = bowling_row.wickets or 0
    runs_conceded = bowling_row.runs_conceded or 0
    balls_bowled = bowling_row.balls_bowled or 0
    economy = round((runs_conceded / balls_bowled * 6), 2) if balls_bowled > 0 else 0

    # Fantasy points
    batting_points = (
        runs * 1 +
        fours * 1 +
        sixes * 2 +
        (8 if runs >= 50 else 0) +
        (16 if runs >= 100 else 0) +
        (6 if strike_rate > 150 else 0)
    )
    bowling_points = (
        wickets * 25 +
        (8 if economy < 6 and balls_bowled > 0 else 0) +
        (4 if 6 <= economy < 8 and balls_bowled > 0 else 0)
    )

    return {
        "player_name": player_name,
        "tournament_year": year,
        "batting": {
            "runs": runs,
            "balls": balls,
            "strike_rate": strike_rate,
            "average": average,
            "fours": fours,
            "sixes": sixes,
        },
        "bowling": {
            "wickets": wickets,
            "economy": economy,
            "balls_bowled": balls_bowled,
        },
        "fantasy_points": batting_points + bowling_points,
    }


def get_team_verdict(total_points: int) -> str:
    if total_points > 2500:
        return "World Class XI — Unstoppable"
    elif total_points > 2000:
        return "Strong XI — Tournament contenders"
    elif total_points > 1500:
        return "Decent XI — Could surprise teams"
    else:
        return "Weak XI — Needs improvement"


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_fantasy_team(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    players = body.get("players", [])
    if len(players) != 11:
        raise HTTPException(status_code=400, detail="You must select exactly 11 players")

    team = FantasyTeam(
        team_name=body.get("team_name", "My Fantasy XI"),
        user_id=current_user.id,
    )
    session.add(team)
    await session.flush()

    player_stats = []
    for p in players:
        name = p.get("name")
        year = p.get("year", "all")
        player = FantasyTeamPlayer(
            fantasy_team_id=team.id,
            player_name=name,
            tournament_year=year,
        )
        session.add(player)
        stats = await get_player_stats(name, year, session)
        player_stats.append(stats)

    await session.commit()
    total_points = sum(p["fantasy_points"] for p in player_stats)

    return {
        "id": team.id,
        "team_name": team.team_name,
        "owner": current_user.username,
        "players": player_stats,
        "total_fantasy_points": total_points,
        "team_rating": min(round(total_points / 30), 100),
        "verdict": get_team_verdict(total_points),
    }


@router.get("")
async def get_my_teams(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(FantasyTeam).where(FantasyTeam.user_id == current_user.id)
    )
    teams = result.scalars().all()
    return {
        "total": len(teams),
        "teams": [{"id": t.id, "team_name": t.team_name, "created_at": t.created_at} for t in teams]
    }


@router.get("/{team_id}")
async def get_fantasy_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id
        )
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")

    players_result = await session.execute(
        select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id)
    )
    players = players_result.scalars().all()

    player_stats = []
    for p in players:
        stats = await get_player_stats(p.player_name, p.tournament_year, session)
        player_stats.append(stats)

    total_points = sum(p["fantasy_points"] for p in player_stats)

    return {
        "id": team.id,
        "team_name": team.team_name,
        "owner": current_user.username,
        "players": player_stats,
        "total_fantasy_points": total_points,
        "team_rating": min(round(total_points / 30), 100),
        "verdict": get_team_verdict(total_points),
    }


@router.put("/{team_id}")
async def update_fantasy_team(
    team_id: int,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id
        )
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")

    if "team_name" in body:
        team.team_name = body["team_name"]

    if "players" in body:
        players = body["players"]
        if len(players) != 11:
            raise HTTPException(status_code=400, detail="You must select exactly 11 players")
        existing = await session.execute(
            select(FantasyTeamPlayer).where(FantasyTeamPlayer.fantasy_team_id == team_id)
        )
        for p in existing.scalars().all():
            await session.delete(p)
        for p in players:
            player = FantasyTeamPlayer(
                fantasy_team_id=team.id,
                player_name=p.get("name"),
                tournament_year=p.get("year", "all"),
            )
            session.add(player)

    await session.commit()
    return {"message": "Team updated successfully", "team_id": team_id}


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fantasy_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    result = await session.execute(
        select(FantasyTeam).where(
            FantasyTeam.id == team_id,
            FantasyTeam.user_id == current_user.id
        )
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Fantasy team not found")
    await session.delete(team)
    await session.commit()

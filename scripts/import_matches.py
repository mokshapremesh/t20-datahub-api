"""
Import T20 World Cup matches (all years) from Cricsheet JSON files.
Usage: PYTHONPATH=. python scripts/import_matches.py
"""
import json
import asyncio
from pathlib import Path
from datetime import date as date_type
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.db.session import async_session
from app.models.match import Match
from app.models.delivery import Delivery

DATA_FOLDER = Path.home() / "Desktop" / "icc_mens_t20_world_cup_json"


def parse_match(data: dict, file_id: str) -> dict | None:
    info = data.get("info", {})
    dates = info.get("dates", [])
    if not dates:
        return None

    raw_date = dates[0]
    match_date = date_type.fromisoformat(str(raw_date))

    teams = info.get("teams", [])
    outcome = info.get("outcome", {})
    winner = outcome.get("winner")
    by = outcome.get("by", {})

    return {
        "cricsheet_id":    file_id,
        "event_name":      info.get("event", {}).get("name"),
        "match_date":      match_date,
        "team1":           teams[0] if len(teams) > 0 else None,
        "team2":           teams[1] if len(teams) > 1 else None,
        "venue":           info.get("venue"),
        "winner":          winner,
        "tournament_year": str(match_date.year),   # uses actual year, not hardcoded
        "stage":           info.get("event", {}).get("stage"),
        "toss_winner":     info.get("toss", {}).get("winner"),
        "toss_decision":   info.get("toss", {}).get("decision"),
        "win_by_runs":     by.get("runs"),
        "win_by_wickets":  by.get("wickets"),
    }


def parse_deliveries(data: dict, match_id: int) -> list[dict]:
    deliveries = []
    innings_list = data.get("innings", [])

    for innings_num, innings in enumerate(innings_list, start=1):
        batting_team = innings.get("team")
        teams = data["info"].get("teams", [])
        bowling_team = next((t for t in teams if t != batting_team), None)

        total_ball_count = 0
        legal_ball_count = 0

        for over_data in innings.get("overs", []):
            over_num = over_data.get("over", 0)
            legal_in_over = 0

            for delivery in over_data.get("deliveries", []):
                runs = delivery.get("runs", {})
                extras = delivery.get("extras", {})
                wickets = delivery.get("wickets", [])

                extras_type = None
                is_legal = True
                if extras:
                    if "wides" in extras:
                        extras_type = "wide"
                        is_legal = False
                    elif "noballs" in extras:
                        extras_type = "noball"
                        is_legal = False
                    elif "byes" in extras:
                        extras_type = "bye"
                    elif "legbyes" in extras:
                        extras_type = "legbye"

                total_ball_count += 1

                if is_legal:
                    legal_ball_count += 1
                    legal_in_over += 1

                is_wicket = len(wickets) > 0
                wicket_type = wickets[0].get("kind") if is_wicket else None
                dismissed = wickets[0].get("player_out") if is_wicket else None

                deliveries.append({
                    "match_id":         match_id,
                    "innings_number":   innings_num,
                    "batting_team":     batting_team,
                    "bowling_team":     bowling_team or "",
                    "ball_in_innings":  total_ball_count,
                    "over":             over_num,
                    "ball_in_over":     legal_in_over if is_legal else 0,
                    "batter":           delivery.get("batter", ""),
                    "bowler":           delivery.get("bowler", ""),
                    "runs_batter":      runs.get("batter", 0),
                    "runs_extras":      runs.get("extras", 0),
                    "runs_total":       runs.get("total", 0),
                    "is_legal":         is_legal,
                    "extras_type":      extras_type,
                    "is_wicket":        is_wicket,
                    "wicket_type":      wicket_type,
                    "dismissed_player": dismissed,
                })

    return deliveries


async def import_all():
    json_files = list(DATA_FOLDER.glob("*.json"))
    print(f"Found {len(json_files)} total files")

    imported = 0
    skipped  = 0
    errors   = 0

    async with async_session() as session:
        for file_path in sorted(json_files):
            file_id = file_path.stem

            try:
                with open(file_path) as f:
                    data = json.load(f)

                match_data = parse_match(data, file_id)
                if match_data is None:
                    skipped += 1
                    continue

                # Skip if match already imported
                existing = await session.execute(
                    select(Match).where(Match.cricsheet_id == file_id)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                # Insert match
                match = Match(**match_data)
                session.add(match)
                await session.flush()

                # Insert deliveries
                delivery_rows = parse_deliveries(data, match.id)
                if delivery_rows:
                    stmt = pg_insert(Delivery).values(delivery_rows)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=["match_id", "innings_number", "ball_in_innings"]
                    )
                    await session.execute(stmt)

                await session.commit()
                print(f"  OK: {match_data['team1']} vs {match_data['team2']} "
                      f"({match_data['match_date']}) [{match_data['tournament_year']}]"
                      f" — {len(delivery_rows)} deliveries")
                imported += 1

            except Exception as e:
                await session.rollback()
                print(f"  ERROR: {file_id} — {e}")
                errors += 1

    print(f"\nDone. Imported: {imported} | Skipped: {skipped} | Errors: {errors}")


if __name__ == "__main__":
    asyncio.run(import_all())
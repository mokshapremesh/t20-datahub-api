from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class ScorecardMatchHeader(BaseModel):
    match_id: int
    team1: str
    team2: str
    match_date: Optional[date] = None
    venue: Optional[str] = None
    stage: Optional[str] = None
    tournament_year: Optional[str] = None
    winner: Optional[str] = None


class InningsSummary(BaseModel):
    runs: int
    wkts: int
    overs: str
    run_rate: float


class BattingRow(BaseModel):
    batter: str
    dismissal: str
    runs: int
    balls: int
    fours: int
    sixes: int
    strike_rate: float


class BowlingRow(BaseModel):
    bowler: str
    overs: str
    maidens: int
    runs: int
    wickets: int
    economy: float


class ExtrasBreakdown(BaseModel):
    total: int
    wides: int
    noballs: int
    byes: int
    legbyes: int
    penalty: int


class FallOfWicket(BaseModel):
    wkt: int
    score: str
    player: str
    over: str


class OverSummary(BaseModel):
    over: int
    runs: int
    wickets: int
    legal_balls: int


class InningsCard(BaseModel):
    innings_no: int
    batting_team: str
    bowling_team: str
    summary: InningsSummary
    batting: list[BattingRow]
    bowling: list[BowlingRow]
    extras: ExtrasBreakdown
    fall_of_wkts: list[FallOfWicket]
    overs: Optional[list[OverSummary]] = None


class ScorecardOut(BaseModel):
    match: ScorecardMatchHeader
    innings: list[InningsCard]
    generated_at: datetime
    version: str = "v1"

    model_config = {
        "json_schema_extra": {
            "example": {
                "match": {
                    "match_id": 198,
                    "team1": "India",
                    "team2": "South Africa",
                    "match_date": "2022-10-30",
                    "venue": "Perth Stadium",
                    "stage": "Group",
                    "tournament_year": "2022",
                    "winner": "India"
                },
                "innings": [
                    {
                        "innings_no": 1,
                        "batting_team": "India",
                        "bowling_team": "South Africa",
                        "summary": {"runs": 133, "wkts": 9, "overs": "20.0", "run_rate": 6.65},
                        "batting": [
                            {"batter": "RG Sharma", "dismissal": "c Markram b Nortje",
                             "runs": 15, "balls": 17, "fours": 1, "sixes": 1, "strike_rate": 88.2}
                        ],
                        "bowling": [
                            {"bowler": "K Rabada", "overs": "4.0", "maidens": 0,
                             "runs": 32, "wickets": 2, "economy": 8.0}
                        ],
                        "extras": {"total": 8, "wides": 5, "noballs": 1, "byes": 2, "legbyes": 0, "penalty": 0},
                        "fall_of_wkts": [
                            {"wkt": 1, "score": "23/1", "player": "RG Sharma", "over": "3.2"}
                        ]
                    }
                ],
                "generated_at": "2026-03-02T21:00:00Z",
                "version": "v1"
            }
        }
    }

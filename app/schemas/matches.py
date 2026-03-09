from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
import re


class InningsScore(BaseModel):
    team: str
    runs: int
    wickets: int
    overs: str

class MatchOut(BaseModel):
    id: int
    cricsheet_id: Optional[str] = None
    match_date: Optional[date] = None
    team1: str
    team2: str
    venue: Optional[str] = None
    stage: Optional[str] = None
    tournament_year: Optional[str] = None
    winner: Optional[str] = None
    toss_winner: Optional[str] = None
    innings_scores: Optional[list[InningsScore]] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 198,
                "cricsheet_id": "1298175",
                "match_date": "2022-10-30",
                "team1": "India",
                "team2": "South Africa",
                "venue": "Perth Stadium",
                "stage": "Group",
                "tournament_year": "2022",
                "winner": "India",
                "toss_winner": "South Africa",
            }
        }
    }


class MatchFilters(BaseModel):
    team: Optional[str] = None
    team2: Optional[str] = None
    year: Optional[str] = None
    stage: Optional[str] = None
    venue: Optional[str] = None


class MatchListOut(BaseModel):
    total: int
    returned: int
    filters: MatchFilters
    matches: list[MatchOut]
    limit: int = 1000
    offset: int = 0


class MatchCreate(BaseModel):
    cricsheet_id: Optional[str] = None
    match_date: Optional[date] = None
    team1: str
    team2: str
    venue: Optional[str] = None
    stage: Optional[str] = None
    tournament_year: Optional[str] = Field(None, pattern=r"^\d{4}$", examples=["2024"])
    winner: Optional[str] = None
    toss_winner: Optional[str] = None


class MatchUpdate(BaseModel):
    match_date: Optional[date] = None
    venue: Optional[str] = None
    stage: Optional[str] = None
    winner: Optional[str] = None
    toss_winner: Optional[str] = None
    tournament_year: Optional[str] = Field(None, pattern=r"^\d{4}$", examples=["2024"])

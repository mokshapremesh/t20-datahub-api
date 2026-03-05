from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime
import re


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
    year: Optional[str] = None
    stage: Optional[str] = None
    venue: Optional[str] = None


class MatchListOut(BaseModel):
    total: int
    returned: int
    limit: int
    offset: int
    filters: MatchFilters
    matches: list[MatchOut]
    links: Optional[dict] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "total": 2,
                "returned": 2,
                "limit": 50,
                "offset": 0,
                "filters": {"team": "India", "year": "2022", "stage": None, "venue": None},
                "matches": [
                    {"id": 198, "team1": "India", "team2": "South Africa",
                     "match_date": "2022-10-30", "venue": "Perth Stadium",
                     "stage": "Group", "tournament_year": "2022",
                     "winner": "India", "toss_winner": "South Africa",
                     "cricsheet_id": "1298175"}
                ]
            }
        }
    }


class MatchCreate(BaseModel):
    cricsheet_id: Optional[str] = None
    match_date: Optional[date] = None
    team1: str
    team2: str
    venue: Optional[str] = None
    stage: Optional[str] = None
    tournament_year: Optional[str] = Field(None, pattern=r"^\\d{4}$", examples=["2024"])
    winner: Optional[str] = None
    toss_winner: Optional[str] = None


class MatchUpdate(BaseModel):
    match_date: Optional[date] = None
    venue: Optional[str] = None
    stage: Optional[str] = None
    winner: Optional[str] = None
    toss_winner: Optional[str] = None
    tournament_year: Optional[str] = Field(None, pattern=r"^\\d{4}$", examples=["2024"])

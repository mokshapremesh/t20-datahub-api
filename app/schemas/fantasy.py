from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FantasyTeamCreate(BaseModel):
    name:        str       = Field(..., examples=["My Dream XI"])
    player_keys: list[str] = Field(default=[], max_length=11, description="Up to 11 player keys from GET /matches/{match_id}/squads")


class CaptainBody(BaseModel):
    player_key: str = Field(..., examples=["V Kohli"])


class TeamRequirements(BaseModel):
    required_players: int = 11
    current_players:  int = 0


class FantasyTeamOut(BaseModel):
    id:               int
    match_id:         Optional[int]      = None
    name:             str
    player_keys:      list[str]          = []
    captain_key:      Optional[str]      = None
    vice_captain_key: Optional[str]      = None
    status:           str                = "DRAFT"
    locked_at:        Optional[datetime] = None
    total_points:     Optional[float]    = None
    requirements:     TeamRequirements   = Field(default_factory=TeamRequirements)
    created_at:       Optional[datetime] = None
    updated_at:       Optional[datetime] = None

    model_config = {"from_attributes": True}


class FantasyTeamListOut(BaseModel):
    total:    int
    returned: int
    teams:    list[FantasyTeamOut]


class LeaderboardEntry(BaseModel):
    rank:         int
    username:     str
    team_name:    str
    total_points: Optional[float] = None
    breakdown:    Optional[list]  = None


class LeaderboardOut(BaseModel):
    match_id:    Optional[int] = None
    year:        Optional[str] = None
    total:       int
    returned:    int
    leaderboard: list[LeaderboardEntry]


class SquadPlayer(BaseModel):
    player_key: str
    team:       str


class SquadOut(BaseModel):
    match_id: int
    matchup:  str
    date:     Optional[str]                = None
    players:  dict[str, list[SquadPlayer]]
    rules:    dict                          = Field(default={"team_size": 11, "captain_multiplier": 2.0, "vice_captain_multiplier": 1.5})
    links:    dict                          = {}

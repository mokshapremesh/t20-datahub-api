from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base


class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"

    id              = Column(Integer, primary_key=True, index=True)
    team_name       = Column(String(100), nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    players         = relationship("FantasyTeamPlayer", back_populates="team", cascade="all, delete")


class FantasyTeamPlayer(Base):
    __tablename__ = "fantasy_team_players"

    id              = Column(Integer, primary_key=True, index=True)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False)
    player_name     = Column(String(100), nullable=False)
    tournament_year = Column(String(4), nullable=False)

    team            = relationship("FantasyTeam", back_populates="players")

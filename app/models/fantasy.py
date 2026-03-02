from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base


class FantasyTeam(Base):
    """User's saved Fantasy XI — reusable across matches"""
    __tablename__ = "fantasy_teams"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_name   = Column(String(100), nullable=False)
    match_id    = Column(Integer, ForeignKey("matches.id"), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    players     = relationship("FantasyTeamPlayer", back_populates="team", cascade="all, delete")
    entries     = relationship("FantasyEntry", back_populates="fantasy_team")


class FantasyTeamPlayer(Base):
    """A player slot in a Fantasy XI"""
    __tablename__ = "fantasy_team_players"

    id              = Column(Integer, primary_key=True, index=True)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False)
    player_name     = Column(String(100), nullable=False)
    tournament_year = Column(String(4), nullable=False)
    role            = Column(String(20), default="PLAYER")  # PLAYER, CAPTAIN, VICE_CAPTAIN
    order           = Column(Integer, default=0)

    team = relationship("FantasyTeam", back_populates="players")


class FantasyEntry(Base):
    """A user's Fantasy XI submitted for a specific match"""
    __tablename__ = "fantasy_entries"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id        = Column(Integer, ForeignKey("matches.id"), nullable=False)
    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False)
    status          = Column(String(20), default="DRAFT")  # DRAFT, SUBMITTED, REVEALED
    total_points    = Column(Float, nullable=True)
    rank_global     = Column(Integer, nullable=True)
    breakdown       = Column(JSON, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    fantasy_team    = relationship("FantasyTeam", back_populates="entries")
# Already in file — just verify match_id column exists on FantasyTeam

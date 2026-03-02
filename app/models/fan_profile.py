from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base

class FanProfile(Base):
    __tablename__ = "fan_profiles"
    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    display_name   = Column(String(100), nullable=True)
    fav_team       = Column(String(100), nullable=True)
    fav_player_key = Column(String(100), nullable=True)
    fav_year       = Column(String(4),   nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

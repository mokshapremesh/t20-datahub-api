from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.session import Base


class MatchPrediction(Base):
    __tablename__ = "match_predictions"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id            = Column(Integer, ForeignKey("matches.id"), nullable=False)
    predicted_winner    = Column(String(100), nullable=False)

    # System calculated probabilities
    win_prob_team1      = Column(Float, nullable=True)
    win_prob_team2      = Column(Float, nullable=True)
    h2h_factor          = Column(Float, nullable=True)
    venue_factor        = Column(Float, nullable=True)
    form_factor         = Column(Float, nullable=True)
    confidence          = Column(String(20), nullable=True)
    model_prediction    = Column(String(100), nullable=True)
    model_agrees        = Column(Boolean, nullable=True)

    # Post match scoring
    actual_winner       = Column(String(100), nullable=True)
    user_correct        = Column(Boolean, nullable=True)
    model_correct       = Column(Boolean, nullable=True)

    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), onupdate=func.now())

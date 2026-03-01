from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.db.session import Base


class PredictionModel(Base):
    """Stores metadata about prediction model versions"""
    __tablename__ = "prediction_models"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100), nullable=False)
    model_type      = Column(String(50), default="statistical")
    features        = Column(JSON, nullable=True)
    trained_on      = Column(String(50), default="2014-2024")
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())


class MatchModelPrediction(Base):
    """Pre-computed model predictions per match"""
    __tablename__ = "match_model_predictions"

    id                  = Column(Integer, primary_key=True, index=True)
    match_id            = Column(Integer, ForeignKey("matches.id"), nullable=False)
    model_id            = Column(Integer, ForeignKey("prediction_models.id"), nullable=False)
    prob_team1          = Column(Float, nullable=False)
    prob_team2          = Column(Float, nullable=False)
    predicted_winner    = Column(String(100), nullable=False)
    explanation         = Column(JSON, nullable=True)
    created_at          = Column(DateTime(timezone=True), server_default=func.now())


class UserPrediction(Base):
    """User's prediction + stake for a match"""
    __tablename__ = "user_predictions"

    id                      = Column(Integer, primary_key=True, index=True)
    user_id                 = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id                = Column(Integer, ForeignKey("matches.id"), nullable=False)
    model_prediction_id     = Column(Integer, ForeignKey("match_model_predictions.id"), nullable=True)
    picked_team             = Column(String(100), nullable=False)
    stake_points            = Column(Integer, default=50)
    odds_multiplier         = Column(Float, nullable=False)
    status                  = Column(String(20), default="OPEN")  # OPEN, LOCKED, SETTLED, CANCELLED
    payout_points           = Column(Integer, nullable=True)
    profit_points           = Column(Integer, nullable=True)
    created_at              = Column(DateTime(timezone=True), server_default=func.now())
    updated_at              = Column(DateTime(timezone=True), onupdate=func.now())


class Transaction(Base):
    """Full audit trail of every points change"""
    __tablename__ = "transactions"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    type            = Column(String(30), nullable=False)  # INITIAL, STAKE, PAYOUT, REFUND
    amount          = Column(Integer, nullable=False)
    balance_after   = Column(Integer, nullable=False)
    reference_type  = Column(String(50), nullable=True)
    reference_id    = Column(Integer, nullable=True)
    note            = Column(String(200), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

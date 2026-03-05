from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, nullable=False, index=True)
    email           = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_admin        = Column(Boolean, default=False)
    role            = Column(String(20), default="user", nullable=False)
    points_balance  = Column(Integer, default=1000)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

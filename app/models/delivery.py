from sqlalchemy import Integer, String, Boolean, ForeignKey, SmallInteger, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class Delivery(Base):
    __tablename__ = "deliveries"

    id:               Mapped[int]        = mapped_column(Integer, primary_key=True)
    match_id:         Mapped[int]        = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    innings_number:   Mapped[int]        = mapped_column(SmallInteger, nullable=False)
    batting_team:     Mapped[str]        = mapped_column(String(64), nullable=False)
    bowling_team:     Mapped[str]        = mapped_column(String(64), nullable=False)
    ball_in_innings:  Mapped[int]        = mapped_column(Integer, nullable=False)
    over:             Mapped[int]        = mapped_column(SmallInteger, nullable=False)
    ball_in_over:     Mapped[int]        = mapped_column(SmallInteger, nullable=False)
    batter:           Mapped[str]        = mapped_column(String(100), nullable=False)
    bowler:           Mapped[str]        = mapped_column(String(100), nullable=False)
    runs_batter:      Mapped[int]        = mapped_column(SmallInteger, default=0)
    runs_extras:      Mapped[int]        = mapped_column(SmallInteger, default=0)
    runs_total:       Mapped[int]        = mapped_column(SmallInteger, default=0)
    is_legal:         Mapped[bool]       = mapped_column(Boolean, default=True)
    extras_type:      Mapped[str | None] = mapped_column(String(20))
    is_wicket:        Mapped[bool]       = mapped_column(Boolean, default=False)
    wicket_type:      Mapped[str | None] = mapped_column(String(50))
    dismissed_player: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        UniqueConstraint("match_id", "innings_number", "ball_in_innings", name="uq_delivery"),
        Index("ix_delivery_match",  "match_id"),
        Index("ix_delivery_batter", "batter"),
        Index("ix_delivery_bowler", "bowler"),
    )
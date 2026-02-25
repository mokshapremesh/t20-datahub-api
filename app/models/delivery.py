from sqlalchemy import Integer, String, ForeignKey, SmallInteger, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base

class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False
    )

    innings: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    over: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ball: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    batting_team: Mapped[str | None] = mapped_column(String(64))
    bowling_team: Mapped[str | None] = mapped_column(String(64))

    striker: Mapped[str | None] = mapped_column(String(80))
    non_striker: Mapped[str | None] = mapped_column(String(80))
    bowler: Mapped[str | None] = mapped_column(String(80))

    runs_batter: Mapped[int] = mapped_column(SmallInteger, default=0)
    runs_extras: Mapped[int] = mapped_column(SmallInteger, default=0)
    runs_total: Mapped[int] = mapped_column(SmallInteger, default=0)

    extras_type: Mapped[str | None] = mapped_column(String(32))
    wicket_kind: Mapped[str | None] = mapped_column(String(32))
    player_dismissed: Mapped[str | None] = mapped_column(String(80))

    match = relationship("Match", backref="deliveries")

    __table_args__ = (
        UniqueConstraint("match_id", "innings", "over", "ball", name="uq_delivery_ball"),
        Index("ix_deliveries_match_innings_over", "match_id", "innings", "over"),
    )
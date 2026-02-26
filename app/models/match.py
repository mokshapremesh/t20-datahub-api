from sqlalchemy import String, Integer, Date, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class Match(Base):
    __tablename__ = "matches"

    id:              Mapped[int]       = mapped_column(Integer, primary_key=True)
    cricsheet_id:    Mapped[str]       = mapped_column(String(32), nullable=False, unique=True)
    event_name:      Mapped[str | None] = mapped_column(String(128))
    match_date:      Mapped[Date | None] = mapped_column(Date)
    team1:           Mapped[str | None] = mapped_column(String(64))
    team2:           Mapped[str | None] = mapped_column(String(64))
    venue:           Mapped[str | None] = mapped_column(String(128))
    winner:          Mapped[str | None] = mapped_column(String(64))
    tournament_year: Mapped[str | None] = mapped_column(String(4))
    stage:           Mapped[str | None] = mapped_column(String(50))
    toss_winner:     Mapped[str | None] = mapped_column(String(64))
    toss_decision:   Mapped[str | None] = mapped_column(String(10))
    win_by_runs:     Mapped[int | None] = mapped_column(Integer)
    win_by_wickets:  Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("cricsheet_id", name="uq_matches_cricsheet_id"),)
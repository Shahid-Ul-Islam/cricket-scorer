"""SQLAlchemy ORM models.

Players hold a name only: no personal data is stored.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cricket_scorer.db import Base
from cricket_scorer.engine import BallEvent, DismissalType, ExtraType


def _str_enum(enum_cls: type[StrEnum]) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        values_callable=lambda cls: [m.value for m in cls],
        length=20,
    )


class TossDecision(StrEnum):
    BAT = "bat"
    BOWL = "bowl"


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    players: Mapped[list[Player]] = relationship(
        back_populates="team", order_by="Player.name", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Team({self.id}, {self.name!r})"


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("team_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))

    team: Mapped[Team] = relationship(back_populates="players")

    def __repr__(self) -> str:
        return f"Player({self.id}, {self.name!r})"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(default=dt.date.today)
    venue: Mapped[str | None] = mapped_column(String(100))
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    overs_per_side: Mapped[int]
    players_per_side: Mapped[int] = mapped_column(default=11)
    max_overs_per_bowler: Mapped[int | None]
    toss_winner_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    toss_decision: Mapped[TossDecision | None] = mapped_column(_str_enum(TossDecision))
    status: Mapped[MatchStatus] = mapped_column(
        _str_enum(MatchStatus), default=MatchStatus.SCHEDULED
    )
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    result: Mapped[str | None] = mapped_column(String(200))

    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])
    toss_winner: Mapped[Team | None] = relationship(foreign_keys=[toss_winner_id])
    winner: Mapped[Team | None] = relationship(foreign_keys=[winner_id])
    innings: Mapped[list[Innings]] = relationship(
        back_populates="match", order_by="Innings.number", cascade="all, delete-orphan"
    )

    @property
    def title(self) -> str:
        return f"{self.home_team.name} v {self.away_team.name}"

    def other_team(self, team_id: int) -> Team:
        return self.away_team if team_id == self.home_team_id else self.home_team


class Innings(Base):
    __tablename__ = "innings"
    __table_args__ = (UniqueConstraint("match_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    number: Mapped[int]  # 1 or 2
    batting_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    bowling_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    closed: Mapped[bool] = mapped_column(default=False)

    match: Mapped[Match] = relationship(back_populates="innings")
    batting_team: Mapped[Team] = relationship(foreign_keys=[batting_team_id])
    bowling_team: Mapped[Team] = relationship(foreign_keys=[bowling_team_id])
    overs: Mapped[list[Over]] = relationship(
        back_populates="innings", order_by="Over.number", cascade="all, delete-orphan"
    )
    balls: Mapped[list[Ball]] = relationship(
        back_populates="innings", order_by="Ball.seq", cascade="all, delete-orphan"
    )

    def events(self) -> list[BallEvent]:
        return [b.to_event() for b in self.balls]


class Over(Base):
    __tablename__ = "overs"
    __table_args__ = (UniqueConstraint("innings_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    innings_id: Mapped[int] = mapped_column(ForeignKey("innings.id"))
    number: Mapped[int]  # 0-based
    bowler_id: Mapped[int] = mapped_column(ForeignKey("players.id"))

    innings: Mapped[Innings] = relationship(back_populates="overs")
    bowler: Mapped[Player] = relationship()
    balls: Mapped[list[Ball]] = relationship(back_populates="over", order_by="Ball.seq")


class Ball(Base):
    """One recorded event. Retirements are events with no over."""

    __tablename__ = "balls"
    __table_args__ = (UniqueConstraint("innings_id", "seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    innings_id: Mapped[int] = mapped_column(ForeignKey("innings.id"))
    over_id: Mapped[int | None] = mapped_column(ForeignKey("overs.id"))
    seq: Mapped[int]  # 0-based order within the innings
    striker_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    non_striker_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    bowler_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    runs: Mapped[int] = mapped_column(default=0)
    extra: Mapped[ExtraType | None] = mapped_column(_str_enum(ExtraType))
    dismissal: Mapped[DismissalType | None] = mapped_column(_str_enum(DismissalType))
    dismissed_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    fielder_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))

    innings: Mapped[Innings] = relationship(back_populates="balls")
    over: Mapped[Over | None] = relationship(back_populates="balls")

    def to_event(self) -> BallEvent:
        return BallEvent(
            striker=self.striker_id,
            non_striker=self.non_striker_id,
            bowler=self.bowler_id,
            runs=self.runs,
            extra=self.extra,
            dismissal=self.dismissal,
            dismissed=self.dismissed_id,
            fielder=self.fielder_id,
        )

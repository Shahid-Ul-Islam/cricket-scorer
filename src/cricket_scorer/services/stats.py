"""Career statistics, computed by replaying completed matches.

Only completed matches count, so a live match never changes a career record
mid-innings.  For a club-sized database replaying everything is cheap; a
cache can come later if it is ever needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from cricket_scorer.engine import BALLS_PER_OVER, format_overs
from cricket_scorer.models import Match, MatchStatus, Player
from cricket_scorer.services.matches import match_innings
from cricket_scorer.services.teams import get_player


@dataclass
class BattingInnings:
    match_id: int
    match_title: str
    date: str
    runs: int
    balls: int
    out: bool


@dataclass
class BowlingInnings:
    match_id: int
    match_title: str
    date: str
    balls: int
    runs: int
    wickets: int

    @property
    def figures(self) -> str:
        return f"{self.wickets}/{self.runs}"


@dataclass
class BattingCareer:
    innings: list[BattingInnings] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.innings)

    @property
    def not_outs(self) -> int:
        return sum(1 for i in self.innings if not i.out)

    @property
    def runs(self) -> int:
        return sum(i.runs for i in self.innings)

    @property
    def balls(self) -> int:
        return sum(i.balls for i in self.innings)

    @property
    def dismissals(self) -> int:
        return self.count - self.not_outs

    @property
    def average(self) -> float | None:
        return round(self.runs / self.dismissals, 2) if self.dismissals else None

    @property
    def strike_rate(self) -> float | None:
        return round(100 * self.runs / self.balls, 2) if self.balls else None

    @property
    def fifties(self) -> int:
        return sum(1 for i in self.innings if 50 <= i.runs < 100)

    @property
    def hundreds(self) -> int:
        return sum(1 for i in self.innings if i.runs >= 100)

    @property
    def highest(self) -> str | None:
        if not self.innings:
            return None
        best = max(self.innings, key=lambda i: (i.runs, not i.out))
        return f"{best.runs}{'' if best.out else '*'}"


@dataclass
class BowlingCareer:
    innings: list[BowlingInnings] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.innings)

    @property
    def balls(self) -> int:
        return sum(i.balls for i in self.innings)

    @property
    def overs(self) -> str:
        return format_overs(self.balls)

    @property
    def runs(self) -> int:
        return sum(i.runs for i in self.innings)

    @property
    def wickets(self) -> int:
        return sum(i.wickets for i in self.innings)

    @property
    def economy(self) -> float | None:
        return round(self.runs * BALLS_PER_OVER / self.balls, 2) if self.balls else None

    @property
    def average(self) -> float | None:
        return round(self.runs / self.wickets, 2) if self.wickets else None

    @property
    def best(self) -> str | None:
        """Best figures: most wickets, then fewest runs."""
        if not self.innings:
            return None
        return min(self.innings, key=lambda i: (-i.wickets, i.runs)).figures


@dataclass
class PlayerStats:
    player: Player
    batting: BattingCareer = field(default_factory=BattingCareer)
    bowling: BowlingCareer = field(default_factory=BowlingCareer)
    match_ids: set[int] = field(default_factory=set)

    @property
    def matches(self) -> int:
        return len(self.match_ids)


def career_stats(session: Session) -> dict[int, PlayerStats]:
    """Stats for every player, keyed by player id."""
    stats = {p.id: PlayerStats(p) for p in session.scalars(select(Player))}
    completed = session.scalars(
        select(Match).where(Match.status == MatchStatus.COMPLETED).order_by(Match.date, Match.id)
    )
    for match in completed:
        title, date = match.title, match.date.isoformat()
        for view in match_innings(match):
            s = view.state
            for b in s.batters.values():
                ps = stats[b.player]
                ps.match_ids.add(match.id)
                ps.batting.innings.append(
                    BattingInnings(match.id, title, date, b.runs, b.balls, b.is_out)
                )
            for bw in s.bowlers.values():
                ps = stats[bw.player]
                ps.match_ids.add(match.id)
                ps.bowling.innings.append(
                    BowlingInnings(match.id, title, date, bw.legal_balls, bw.runs, bw.wickets)
                )
            for event in s.events:
                if event.fielder is not None:
                    stats[event.fielder].match_ids.add(match.id)
    return stats


def player_stats(session: Session, player_id: int) -> PlayerStats:
    get_player(session, player_id)  # raises NotFoundError
    return career_stats(session)[player_id]

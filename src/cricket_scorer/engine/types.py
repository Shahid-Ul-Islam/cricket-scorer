"""Value types for the scoring engine.

The engine is pure: no database, no web.  An innings is a list of
:class:`BallEvent` objects and its state is obtained by replaying them.
Players are referred to by opaque integer ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

BALLS_PER_OVER = 6


class ExtraType(StrEnum):
    WIDE = "wide"
    NO_BALL = "no_ball"
    BYE = "bye"
    LEG_BYE = "leg_bye"


class DismissalType(StrEnum):
    BOWLED = "bowled"
    CAUGHT = "caught"
    LBW = "lbw"
    RUN_OUT = "run_out"
    STUMPED = "stumped"
    HIT_WICKET = "hit_wicket"
    RETIRED_HURT = "retired_hurt"
    RETIRED_OUT = "retired_out"

    @property
    def credited_to_bowler(self) -> bool:
        return self in BOWLER_DISMISSALS

    @property
    def is_retirement(self) -> bool:
        return self in (DismissalType.RETIRED_HURT, DismissalType.RETIRED_OUT)

    @property
    def counts_as_wicket(self) -> bool:
        """Retired hurt is not a wicket: the batter may resume later."""
        return self is not DismissalType.RETIRED_HURT

    @property
    def needs_fielder(self) -> bool:
        return self in (DismissalType.CAUGHT, DismissalType.STUMPED)


BOWLER_DISMISSALS = frozenset(
    {
        DismissalType.BOWLED,
        DismissalType.CAUGHT,
        DismissalType.LBW,
        DismissalType.STUMPED,
        DismissalType.HIT_WICKET,
    }
)


@dataclass(frozen=True, slots=True)
class BallEvent:
    """One recorded event in an innings.

    ``runs`` means:

    * no extra / no-ball: runs scored off the bat;
    * bye / leg-bye: byes run;
    * wide: runs run (or 4 for a boundary) *in addition to* the one-run penalty.

    A retirement (``RETIRED_HURT`` / ``RETIRED_OUT``) is recorded as an event
    that is not a delivery: it must carry no runs and no extra.
    """

    striker: int
    non_striker: int
    bowler: int
    runs: int = 0
    extra: ExtraType | None = None
    dismissal: DismissalType | None = None
    dismissed: int | None = None
    fielder: int | None = None

    @property
    def is_delivery(self) -> bool:
        return not (self.dismissal is not None and self.dismissal.is_retirement)

    @property
    def is_legal(self) -> bool:
        """Wides and no-balls are not legal deliveries and do not count toward the over."""
        return self.is_delivery and self.extra not in (ExtraType.WIDE, ExtraType.NO_BALL)

    @property
    def penalty(self) -> int:
        return 1 if self.extra in (ExtraType.WIDE, ExtraType.NO_BALL) else 0

    @property
    def total_runs(self) -> int:
        return self.runs + self.penalty

    @property
    def bat_runs(self) -> int:
        return self.runs if self.extra in (None, ExtraType.NO_BALL) else 0

    @property
    def extra_runs(self) -> int:
        return self.total_runs - self.bat_runs

    @property
    def bowler_runs(self) -> int:
        """Runs charged to the bowler: everything except byes and leg-byes."""
        return 0 if self.extra in (ExtraType.BYE, ExtraType.LEG_BYE) else self.total_runs

    @property
    def faced_by_striker(self) -> bool:
        """A wide is not a ball faced; a no-ball is."""
        return self.is_delivery and self.extra is not ExtraType.WIDE

    @property
    def out_player(self) -> int | None:
        if self.dismissal is None:
            return None
        return self.dismissed if self.dismissed is not None else self.striker


@dataclass(frozen=True, slots=True)
class InningsConfig:
    overs: int
    players_per_side: int = 11
    target: int | None = None
    max_overs_per_bowler: int | None = None

    @property
    def max_balls(self) -> int:
        return self.overs * BALLS_PER_OVER

    @property
    def max_wickets(self) -> int:
        return self.players_per_side - 1


class IllegalEventError(ValueError):
    """Raised when an event breaks the rules given the current innings state."""


def format_overs(legal_balls: int) -> str:
    """Format a ball count the cricket way: 15 balls -> ``"2.3"``."""
    return f"{legal_balls // BALLS_PER_OVER}.{legal_balls % BALLS_PER_OVER}"

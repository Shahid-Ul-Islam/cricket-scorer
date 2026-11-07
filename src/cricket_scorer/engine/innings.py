"""Innings state machine.

:class:`Innings` holds the list of recorded events and the state derived from
them.  Every event is validated against the current state before it is
applied, so a stored list of events can always be replayed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cricket_scorer.engine.types import (
    BALLS_PER_OVER,
    BallEvent,
    DismissalType,
    ExtraType,
    IllegalEventError,
    InningsConfig,
    format_overs,
)

MAX_RUNS_PER_BALL = 7  # e.g. three run plus four overthrows


@dataclass(slots=True)
class BatterStats:
    player: int
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    dismissal: DismissalType | None = None
    bowler: int | None = None
    fielder: int | None = None

    @property
    def is_out(self) -> bool:
        return self.dismissal is not None and self.dismissal.counts_as_wicket

    @property
    def strike_rate(self) -> float | None:
        return round(100 * self.runs / self.balls, 2) if self.balls else None


@dataclass(slots=True)
class BowlerStats:
    player: int
    legal_balls: int = 0
    maidens: int = 0
    runs: int = 0
    wickets: int = 0
    wides: int = 0
    no_balls: int = 0
    dots: int = 0

    @property
    def overs(self) -> str:
        return format_overs(self.legal_balls)

    @property
    def economy(self) -> float | None:
        if not self.legal_balls:
            return None
        return round(self.runs * BALLS_PER_OVER / self.legal_balls, 2)


@dataclass(frozen=True, slots=True)
class FallOfWicket:
    number: int
    runs: int
    overs: str
    player: int


@dataclass(frozen=True, slots=True)
class AppliedEvent:
    """An event together with where it fell in the innings."""

    event: BallEvent
    over_index: int  # 0-based over the event belongs to
    runs: int  # team score after the event
    wickets: int  # team wickets after the event
    free_hit: bool  # whether this delivery was a free hit

    @property
    def label(self) -> str:
        return ball_label(self.event)


def ball_label(e: BallEvent) -> str:
    """Short scorebook symbol for a delivery, e.g. ``4``, ``2wd``, ``nb+4``, ``1lb``, ``W``."""
    if e.dismissal is DismissalType.RETIRED_HURT:
        return "RH"
    if e.dismissal is DismissalType.RETIRED_OUT:
        return "RO"
    match e.extra:
        case ExtraType.WIDE:
            text = f"{e.total_runs}wd"
        case ExtraType.NO_BALL:
            text = f"nb+{e.runs}" if e.runs else "nb"
        case ExtraType.BYE:
            text = f"{e.runs}b"
        case ExtraType.LEG_BYE:
            text = f"{e.runs}lb"
        case _:
            text = str(e.runs)
    if e.dismissal is not None:
        return "W" if text == "0" else f"{text}+W"
    return text


@dataclass
class _Partnership:
    runs: int = 0
    balls: int = 0


class Innings:
    def __init__(self, config: InningsConfig, events: Iterable[BallEvent] = ()) -> None:
        self.config = config
        self._events: list[BallEvent] = []
        self._reset()
        for event in events:
            self.record(event)

    # ------------------------------------------------------------------ state

    def _reset(self) -> None:
        self.runs = 0
        self.wickets = 0
        self.legal_balls = 0
        self.extras: dict[ExtraType, int] = dict.fromkeys(ExtraType, 0)
        self.striker: int | None = None
        self.non_striker: int | None = None
        self.batters: dict[int, BatterStats] = {}  # insertion order == batting order
        self.bowlers: dict[int, BowlerStats] = {}
        self.over_bowlers: list[int] = []  # bowler of each over, by index
        self.applied: list[AppliedEvent] = []
        self.fall_of_wickets: list[FallOfWicket] = []
        self.partnership = _Partnership()
        self.free_hit = False
        self.closed = False
        self._over_bowler_runs = 0

    @property
    def events(self) -> tuple[BallEvent, ...]:
        return tuple(self._events)

    @property
    def overs(self) -> str:
        return format_overs(self.legal_balls)

    @property
    def balls_remaining(self) -> int:
        return max(self.config.max_balls - self.legal_balls, 0)

    @property
    def run_rate(self) -> float | None:
        if not self.legal_balls:
            return None
        return round(self.runs * BALLS_PER_OVER / self.legal_balls, 2)

    @property
    def runs_required(self) -> int | None:
        if self.config.target is None:
            return None
        return max(self.config.target - self.runs, 0)

    @property
    def required_rate(self) -> float | None:
        required = self.runs_required
        if required is None or not self.balls_remaining:
            return None
        return round(required * BALLS_PER_OVER / self.balls_remaining, 2)

    @property
    def total_extras(self) -> int:
        return sum(self.extras.values())

    @property
    def target_reached(self) -> bool:
        return self.config.target is not None and self.runs >= self.config.target

    @property
    def all_out(self) -> bool:
        return self.wickets >= self.config.max_wickets

    @property
    def overs_complete(self) -> bool:
        return self.legal_balls >= self.config.max_balls

    @property
    def is_complete(self) -> bool:
        return self.closed or self.overs_complete or self.all_out or self.target_reached

    @property
    def current_over_index(self) -> int:
        return self.legal_balls // BALLS_PER_OVER

    @property
    def over_in_progress(self) -> bool:
        return len(self.over_bowlers) > self.current_over_index

    @property
    def current_bowler(self) -> int | None:
        """Bowler of the over in progress, or ``None`` if a new over is due."""
        return self.over_bowlers[self.current_over_index] if self.over_in_progress else None

    @property
    def previous_over_bowler(self) -> int | None:
        """Bowler of the last completed over, who may not bowl the next one."""
        idx = self.current_over_index - 1
        return self.over_bowlers[idx] if 0 <= idx < len(self.over_bowlers) else None

    @property
    def this_over(self) -> list[AppliedEvent]:
        """Deliveries of the over in progress, or of the last over if a new one is due."""
        if not self.applied:
            return []
        idx = self.applied[-1].over_index
        return [a for a in self.applied if a.over_index == idx and a.event.is_delivery]

    def overs_by(self, bowler: int) -> int:
        return self.over_bowlers.count(bowler)

    # --------------------------------------------------------------- mutation

    def record(self, event: BallEvent) -> None:
        """Validate and apply ``event``; raises :class:`IllegalEventError`."""
        self._validate(event)
        self._apply(event)
        self._events.append(event)

    def close(self) -> None:
        """End the innings early (e.g. no fit batters left)."""
        self.closed = True

    # ------------------------------------------------------------- validation

    def _validate(self, e: BallEvent) -> None:
        if self.is_complete:
            raise IllegalEventError("innings is complete")
        self._validate_runs(e)
        self._validate_batters(e)
        self._validate_bowler(e)

    @staticmethod
    def _validate_runs(e: BallEvent) -> None:
        if not 0 <= e.runs <= MAX_RUNS_PER_BALL:
            raise IllegalEventError(f"runs must be between 0 and {MAX_RUNS_PER_BALL}")
        if e.extra in (ExtraType.BYE, ExtraType.LEG_BYE) and e.runs == 0:
            raise IllegalEventError("byes and leg-byes need at least one run")

    def _validate_batters(self, e: BallEvent) -> None:
        if e.striker == e.non_striker:
            raise IllegalEventError("striker and non-striker must be different players")
        at_crease = {p for p in (self.striker, self.non_striker) if p is not None}
        named = {e.striker, e.non_striker}
        missing = at_crease - named
        if missing:
            raise IllegalEventError(f"player {missing.pop()} is still batting")
        for player in named - at_crease:
            if not self._can_come_in(player):
                raise IllegalEventError(f"player {player} cannot bat again")
        new_players = sum(1 for p in named if p not in self.batters)
        if len(self.batters) + new_players > self.config.players_per_side:
            raise IllegalEventError("no batters left")

    def _can_come_in(self, player: int) -> bool:
        return player not in self.batters

    def _validate_bowler(self, e: BallEvent) -> None:
        if e.bowler in (e.striker, e.non_striker):
            raise IllegalEventError("bowler cannot also be batting")
        if self.over_in_progress:
            if e.bowler != self.current_bowler:
                raise IllegalEventError(
                    f"over in progress is being bowled by player {self.current_bowler}"
                )
            return
        if e.bowler == self.previous_over_bowler:
            raise IllegalEventError("a bowler cannot bowl consecutive overs")
        limit = self.config.max_overs_per_bowler
        if limit is not None and self.overs_by(e.bowler) >= limit:
            raise IllegalEventError(f"player {e.bowler} has bowled the maximum {limit} overs")

    # ------------------------------------------------------------ application

    def _apply(self, e: BallEvent) -> None:
        for player in (e.striker, e.non_striker):
            self.batters.setdefault(player, BatterStats(player))
        self.striker, self.non_striker = e.striker, e.non_striker

        over_index = self.current_over_index
        if not self.over_in_progress:
            self.over_bowlers.append(e.bowler)
            self._over_bowler_runs = 0
        was_free_hit = self.free_hit

        self._score_delivery(e)
        if e.runs % 2:
            self._swap_strike()
        over_complete = e.is_legal and self.legal_balls % BALLS_PER_OVER == 0
        if over_complete:
            if self._over_bowler_runs == 0:
                self.bowlers[e.bowler].maidens += 1
            self._swap_strike()

        self._update_free_hit(e)
        self.applied.append(AppliedEvent(e, over_index, self.runs, self.wickets, was_free_hit))

    def _update_free_hit(self, e: BallEvent) -> None:
        """The delivery after a no-ball is a free hit.  If that delivery is itself
        a wide or no-ball, the free hit carries over to the next one."""
        if e.extra is ExtraType.NO_BALL:
            self.free_hit = True
        elif e.extra is not ExtraType.WIDE:
            self.free_hit = False

    def _score_delivery(self, e: BallEvent) -> None:
        self.runs += e.total_runs
        if e.extra is not None:
            self.extras[e.extra] += e.extra_runs

        batter = self.batters[e.striker]
        batter.runs += e.bat_runs
        if e.faced_by_striker:
            batter.balls += 1
        if e.bat_runs == 4:
            batter.fours += 1
        elif e.bat_runs == 6:
            batter.sixes += 1

        bowler = self.bowlers.setdefault(e.bowler, BowlerStats(e.bowler))
        bowler.runs += e.bowler_runs
        self._over_bowler_runs += e.bowler_runs
        if e.extra is ExtraType.WIDE:
            bowler.wides += 1
        elif e.extra is ExtraType.NO_BALL:
            bowler.no_balls += 1

        self.partnership.runs += e.total_runs
        if e.is_legal:
            self.legal_balls += 1
            bowler.legal_balls += 1
            self.partnership.balls += 1
            if e.bowler_runs == 0:
                bowler.dots += 1

    def _swap_strike(self) -> None:
        self.striker, self.non_striker = self.non_striker, self.striker

"""Test helper that drives an :class:`Innings` like a scorer would.

Batting side players are 1..11 (openers 1 and 2), bowlers are 101, 102, ...
"""

from __future__ import annotations

from cricket_scorer.engine import BallEvent, InningsConfig
from cricket_scorer.engine.innings import Innings

A, B, C, D = 1, 2, 3, 4
BOWLER_1, BOWLER_2, BOWLER_3 = 101, 102, 103


class Scorer:
    """Fills in striker/non-striker from the innings state, brings in the next
    batter for an empty slot, and alternates two bowlers each over."""

    def __init__(self, innings: Innings) -> None:
        self.innings = innings
        self.bowler = BOWLER_1
        self.next_batter = 1

    def ball(self, runs: int = 0, **kw) -> Innings:
        inn = self.innings
        striker = kw.pop("striker", inn.striker)
        non_striker = kw.pop("non_striker", inn.non_striker)
        if striker is None:
            striker = self._new_batter()
        if non_striker is None:
            non_striker = self._new_batter()
        if not inn.over_in_progress and inn.previous_over_bowler == self.bowler:
            self.bowler = BOWLER_2 if self.bowler == BOWLER_1 else BOWLER_1
        bowler = kw.pop("bowler", self.bowler)
        inn.record(BallEvent(striker, non_striker, bowler, runs=runs, **kw))
        return inn

    def balls(self, *runs: int) -> Innings:
        for r in runs:
            self.ball(r)
        return self.innings

    def _new_batter(self) -> int:
        player = self.next_batter
        self.next_batter += 1
        return player


def make(overs: int = 5, **kw) -> tuple[Innings, Scorer]:
    inn = Innings(InningsConfig(overs=overs, **kw))
    return inn, Scorer(inn)

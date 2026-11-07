from sqlalchemy.orm import Session

from cricket_scorer.engine import BallEvent, DismissalType
from cricket_scorer.models import TossDecision
from cricket_scorer.services import matches
from cricket_scorer.services.stats import (
    BattingCareer,
    BattingInnings,
    BowlingCareer,
    BowlingInnings,
    career_stats,
)
from factories import Fixture, make_match


def bi(runs: int, balls: int, out: bool = True) -> BattingInnings:
    return BattingInnings(1, "m", "2026-01-01", runs, balls, out)


def wi(wickets: int, runs: int, balls: int = 24) -> BowlingInnings:
    return BowlingInnings(1, "m", "2026-01-01", balls, runs, wickets)


class TestBattingCareer:
    def test_empty(self) -> None:
        c = BattingCareer()
        assert (c.count, c.runs, c.average, c.strike_rate, c.highest) == (0, 0, None, None, None)

    def test_average_uses_dismissals_not_innings(self) -> None:
        c = BattingCareer([bi(30, 20), bi(20, 10, out=False), bi(10, 10)])
        assert c.runs == 60 and c.not_outs == 1 and c.average == 30.0
        assert c.strike_rate == 150.0

    def test_never_dismissed_has_no_average(self) -> None:
        assert BattingCareer([bi(12, 10, out=False)]).average is None

    def test_milestones_and_highest(self) -> None:
        c = BattingCareer([bi(49, 40), bi(50, 40), bi(99, 70, out=False), bi(100, 80), bi(99, 60)])
        assert c.fifties == 3 and c.hundreds == 1
        assert c.highest == "100"
        assert BattingCareer([bi(99, 70), bi(99, 60, out=False)]).highest == "99*"


class TestBowlingCareer:
    def test_figures(self) -> None:
        c = BowlingCareer([wi(2, 30), wi(3, 25), wi(3, 18), wi(0, 10)])
        assert c.wickets == 8 and c.runs == 83
        assert c.best == "3/18"
        assert c.overs == "16.0"
        assert c.economy == round(83 / 16, 2)
        assert c.average == round(83 / 8, 2)

    def test_empty(self) -> None:
        c = BowlingCareer()
        assert (c.best, c.economy, c.average, c.overs) == (None, None, None, "0.0")


def record(fx: Fixture, **kw) -> None:
    innings = matches.current_innings(fx.match)
    assert innings is not None
    state = matches.innings_state(fx.match, innings)
    kw.setdefault("striker", state.striker)
    kw.setdefault("non_striker", state.non_striker)
    matches.record_ball(fx.session, fx.match, BallEvent(**kw))


def test_career_stats_from_completed_match(session: Session) -> None:
    fx = make_match(session, overs=1, toss=TossDecision.BAT)
    h1, h2, h3, a1, a2, a5 = fx.h(1), fx.h(2), fx.h(3), fx.a(1), fx.a(2), fx.a(5)
    record(fx, striker=h1, non_striker=h2, bowler=a1, runs=4)
    record(fx, bowler=a1, dismissal=DismissalType.CAUGHT, fielder=a5)  # H1 c A5 b A1
    record(fx, striker=h3, non_striker=h2, bowler=a1, runs=0)
    for _ in range(3):
        record(fx, bowler=a1, runs=0)  # over ends: 4/1, target 5
    # Live match: not counted yet.
    assert career_stats(session)[h1].batting.count == 0

    record(fx, striker=a1, non_striker=a2, bowler=h1, runs=1)
    record(fx, bowler=h1, runs=4)
    assert fx.match.result is not None

    stats = career_stats(session)
    assert stats[h1].batting.runs == 4 and stats[h1].batting.dismissals == 1
    assert stats[h1].bowling.best == "0/5" and stats[h1].matches == 1
    assert stats[a1].bowling.wickets == 1 and stats[a1].bowling.best == "1/4"
    assert stats[a1].batting.runs == 1 and stats[a1].batting.not_outs == 1
    assert stats[a5].matches == 1  # fielded only
    assert stats[fx.h(11)].matches == 0

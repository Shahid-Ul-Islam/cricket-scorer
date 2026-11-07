import pytest
from sqlalchemy.orm import Session

from cricket_scorer.engine import BallEvent, DismissalType, ExtraType
from cricket_scorer.engine.innings import BatterStats
from cricket_scorer.services import matches
from cricket_scorer.services.scorecard import build_scorecard, how_out
from factories import Fixture, bowl_over, make_match

NAMES = {1: "Ali", 2: "Ben", 3: "Cal"}


@pytest.mark.parametrize(
    ("dismissal", "bowler", "fielder", "expected"),
    [
        (None, None, None, "not out"),
        (DismissalType.BOWLED, 2, None, "b Ben"),
        (DismissalType.CAUGHT, 2, 3, "c Cal b Ben"),
        (DismissalType.CAUGHT, 2, 2, "c & b Ben"),
        (DismissalType.CAUGHT, 2, None, "caught b Ben"),
        (DismissalType.LBW, 2, None, "lbw b Ben"),
        (DismissalType.STUMPED, 2, 3, "st Cal b Ben"),
        (DismissalType.HIT_WICKET, 2, None, "hit wicket b Ben"),
        (DismissalType.RUN_OUT, None, 3, "run out (Cal)"),
        (DismissalType.RUN_OUT, None, None, "run out"),
        (DismissalType.RETIRED_HURT, None, None, "retired hurt"),
        (DismissalType.RETIRED_OUT, None, None, "retired out"),
    ],
)
def test_how_out(dismissal, bowler, fielder, expected) -> None:
    b = BatterStats(1, dismissal=dismissal, bowler=bowler, fielder=fielder)
    assert how_out(b, NAMES) == expected


def ball(fx: Fixture, **kw) -> None:
    innings = matches.current_innings(fx.match)
    assert innings is not None
    state = matches.innings_state(fx.match, innings)
    kw.setdefault("striker", state.striker)
    kw.setdefault("non_striker", state.non_striker)
    matches.record_ball(fx.session, fx.match, BallEvent(**kw))


def test_scorecard(session: Session) -> None:
    fx = make_match(session, overs=2)
    bowler = fx.a(1)
    ball(fx, striker=fx.h(1), non_striker=fx.h(2), bowler=bowler, runs=4)
    ball(fx, bowler=bowler, runs=0, extra=ExtraType.WIDE)
    ball(fx, bowler=bowler, runs=1, extra=ExtraType.LEG_BYE)
    ball(fx, bowler=bowler, dismissal=DismissalType.CAUGHT, fielder=fx.a(7))
    ball(fx, striker=fx.h(3), bowler=bowler, runs=6)

    card = build_scorecard(fx.match)
    assert card.title == "Home CC v Away CC"
    assert card.toss == "Home CC won the toss and elected to bat"
    inn = card.innings[0]
    assert inn.total == "12/1" and inn.overs == "0.4"
    assert inn.extras_detail == "lb 1, w 1" and inn.total_extras == 2
    assert [(b.name, b.how_out, b.runs, b.balls) for b in inn.batting] == [
        ("H1", "not out", 4, 2),  # the leg-bye counts as a ball faced
        ("H2", "c A7 b A1", 0, 1),
        ("H3", "not out", 6, 1),
    ]
    (bw,) = inn.bowling
    assert (bw.name, bw.overs, bw.runs, bw.wickets, bw.wides) == ("A1", "0.4", 11, 1, 1)
    assert [(f.number, f.runs, f.name, f.overs) for f in inn.fall_of_wickets] == [
        (1, 6, "H2", "0.3")
    ]


def test_scorecard_second_innings_has_target(session: Session) -> None:
    fx = make_match(session, overs=1)
    bowl_over(fx, fx.a(1), [1] * 6)
    card = build_scorecard(fx.match)
    assert len(card.innings) == 2
    assert card.innings[1].target == 7 and card.innings[1].batting == []

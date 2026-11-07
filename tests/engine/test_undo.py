import pytest
from scoring_helpers import BOWLER_1, BOWLER_2, A, B, C, make

from cricket_scorer.engine import BallEvent, DismissalType, ExtraType, IllegalEventError
from cricket_scorer.engine.innings import Innings


def snapshot(inn: Innings) -> tuple:
    return (
        inn.runs,
        inn.wickets,
        inn.legal_balls,
        inn.striker,
        inn.non_striker,
        inn.free_hit,
        dict(inn.extras),
        {p: (b.runs, b.balls, b.dismissal) for p, b in inn.batters.items()},
        {p: (b.legal_balls, b.runs, b.wickets, b.maidens) for p, b in inn.bowlers.items()},
        len(inn.fall_of_wickets),
        (inn.partnership.runs, inn.partnership.balls),
        tuple(inn.over_bowlers),
    )


def test_undo_with_nothing_recorded() -> None:
    inn, _ = make()
    with pytest.raises(IllegalEventError, match="nothing to undo"):
        inn.undo()


def test_undo_returns_the_removed_event() -> None:
    inn, s = make()
    s.ball(4)
    assert inn.undo() == BallEvent(A, B, BOWLER_1, runs=4)
    assert inn.events == ()
    assert inn.runs == 0 and inn.striker is None


@pytest.mark.parametrize(
    "last",
    [
        {"runs": 1},
        {"runs": 4},
        {"runs": 1, "extra": ExtraType.WIDE},
        {"runs": 2, "extra": ExtraType.NO_BALL},
        {"runs": 1, "extra": ExtraType.LEG_BYE},
        {"runs": 0, "dismissal": DismissalType.BOWLED},
        {"runs": 1, "dismissal": DismissalType.RUN_OUT, "dismissed": B},
        {"runs": 0, "dismissal": DismissalType.RETIRED_HURT},
    ],
)
def test_undo_restores_previous_state(last: dict) -> None:
    inn, s = make()
    s.balls(1, 0, 4, 0)
    before = snapshot(inn)
    s.ball(**last)
    assert snapshot(inn) != before
    inn.undo()
    assert snapshot(inn) == before


def test_undo_last_ball_of_over_restores_strike_and_bowler() -> None:
    inn, s = make()
    s.balls(0, 0, 0, 0, 0)
    s.ball(0)
    assert inn.current_bowler is None and inn.striker == B
    inn.undo()
    assert inn.overs == "0.5"
    assert inn.current_bowler == BOWLER_1
    assert inn.striker == A
    assert inn.bowlers[BOWLER_1].maidens == 0


def test_undo_first_ball_of_new_over_frees_bowler_choice() -> None:
    inn, s = make()
    s.balls(0, 0, 0, 0, 0, 0)
    s.ball(0)  # BOWLER_2 starts over 2
    inn.undo()
    assert inn.current_bowler is None
    assert inn.over_bowlers == [BOWLER_1]
    assert BOWLER_2 not in inn.bowlers


def test_undo_wicket_brings_batter_back() -> None:
    inn, s = make()
    s.ball(0)
    s.ball(0, dismissal=DismissalType.BOWLED)
    inn.undo()
    assert inn.wickets == 0
    assert inn.striker == A
    inn.record(BallEvent(A, B, BOWLER_1, runs=1))  # A can bat on
    assert C not in inn.batters


def test_undo_restores_free_hit() -> None:
    inn, s = make()
    s.ball(0, extra=ExtraType.NO_BALL)
    s.ball(1)
    assert not inn.free_hit
    inn.undo()
    assert inn.free_hit


def test_undo_reopens_completed_innings() -> None:
    inn, s = make(overs=1, target=4)
    s.ball(4)
    assert inn.is_complete
    inn.undo()
    assert not inn.is_complete


def test_undo_reopens_closed_innings() -> None:
    inn, s = make()
    s.ball(1)
    inn.close()
    inn.undo()
    assert not inn.closed


def test_repeated_undo_back_to_start() -> None:
    inn, s = make()
    s.balls(1, 2, 3, 4, 6, 0, 1)
    for _ in range(7):
        inn.undo()
    assert snapshot(inn) == snapshot(make()[0])


def test_replay_from_events_matches_live_state() -> None:
    inn, s = make()
    s.balls(1, 4, 0)
    s.ball(0, extra=ExtraType.NO_BALL)
    s.ball(2, dismissal=DismissalType.RUN_OUT)
    s.balls(1, 1, 6)
    replayed = Innings(inn.config, inn.events)
    assert snapshot(replayed) == snapshot(inn)

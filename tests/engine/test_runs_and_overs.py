import pytest
from scoring_helpers import BOWLER_1, BOWLER_2, BOWLER_3, A, B, C, make

from cricket_scorer.engine import BallEvent, IllegalEventError


def test_runs_accumulate_and_credit_batter_and_bowler() -> None:
    inn, s = make()
    s.balls(1, 4, 0, 6)
    assert inn.runs == 11
    assert inn.legal_balls == 4
    assert inn.overs == "0.4"
    assert inn.batters[A].runs == 1 and inn.batters[A].balls == 1
    assert inn.batters[B].runs == 10 and inn.batters[B].balls == 3
    assert inn.batters[B].fours == 1 and inn.batters[B].sixes == 1
    assert inn.bowlers[BOWLER_1].runs == 11
    assert inn.bowlers[BOWLER_1].dots == 1


@pytest.mark.parametrize(
    ("runs", "striker_after"),
    [(0, A), (1, B), (2, A), (3, B), (4, A), (5, B), (6, A)],
)
def test_strike_rotates_on_odd_runs(runs: int, striker_after: int) -> None:
    inn, s = make()
    s.ball(runs)
    assert inn.striker == striker_after


def test_strike_rotates_at_end_of_over() -> None:
    inn, s = make()
    s.balls(0, 0, 0, 0, 0, 0)
    assert inn.overs == "1.0"
    assert (inn.striker, inn.non_striker) == (B, A)


def test_single_off_last_ball_keeps_striker() -> None:
    inn, s = make()
    s.balls(0, 0, 0, 0, 0, 1)
    # A ran to the other end, then ends change at the over: A faces again.
    assert inn.striker == A


def test_maiden_recorded() -> None:
    inn, s = make()
    s.balls(0, 0, 0, 0, 0, 0)
    s.balls(1, 0, 0, 0, 0, 0)
    assert inn.bowlers[BOWLER_1].maidens == 1
    assert inn.bowlers[BOWLER_2].maidens == 0


def test_bowler_cannot_bowl_consecutive_overs() -> None:
    _inn, s = make()
    s.balls(0, 0, 0, 0, 0, 0)
    with pytest.raises(IllegalEventError, match="consecutive"):
        s.ball(0, bowler=BOWLER_1)


def test_bowler_cannot_change_mid_over() -> None:
    _inn, s = make()
    s.ball(0)
    with pytest.raises(IllegalEventError, match="being bowled by"):
        s.ball(0, bowler=BOWLER_3)


def test_max_overs_per_bowler() -> None:
    _inn, s = make(overs=5, max_overs_per_bowler=1)
    s.balls(*[0] * 6)  # BOWLER_1
    s.balls(*[0] * 6)  # BOWLER_2
    with pytest.raises(IllegalEventError, match="maximum"):
        s.ball(0, bowler=BOWLER_1)


def test_current_and_previous_bowler() -> None:
    inn, s = make()
    assert inn.current_bowler is None
    s.ball(0)
    assert inn.current_bowler == BOWLER_1
    s.balls(0, 0, 0, 0, 0)
    assert inn.current_bowler is None
    assert inn.previous_over_bowler == BOWLER_1


def test_innings_ends_when_overs_run_out() -> None:
    inn, s = make(overs=1)
    s.balls(0, 0, 0, 0, 0, 0)
    assert inn.is_complete and inn.overs_complete
    with pytest.raises(IllegalEventError, match="complete"):
        s.ball(0)


def test_chase_ends_when_target_reached() -> None:
    inn, s = make(overs=2, target=10)
    s.balls(4, 4)
    assert not inn.is_complete
    assert inn.runs_required == 2
    assert inn.required_rate == pytest.approx(1.2)  # 2 runs off 10 balls
    s.ball(2)
    assert inn.is_complete and inn.target_reached


def test_run_rate() -> None:
    inn, s = make()
    assert inn.run_rate is None
    s.balls(4, 4, 4)
    assert inn.run_rate == 24.0


def test_partnership_tracks_runs_and_balls() -> None:
    inn, s = make()
    s.balls(1, 2, 0)
    assert (inn.partnership.runs, inn.partnership.balls) == (3, 3)


def test_this_over_shows_current_then_last_completed_over() -> None:
    inn, s = make()
    s.balls(1, 0, 4)
    assert [a.label for a in inn.this_over] == ["1", "0", "4"]
    s.balls(0, 0, 6)
    assert [a.label for a in inn.this_over] == ["1", "0", "4", "0", "0", "6"]
    s.ball(2)
    assert [a.label for a in inn.this_over] == ["2"]


def test_batters_must_stay_at_crease() -> None:
    inn, s = make()
    s.ball(0)
    with pytest.raises(IllegalEventError, match="still batting"):
        inn.record(BallEvent(A, C, BOWLER_1))


def test_scorer_may_correct_ends() -> None:
    inn, s = make()
    s.ball(0)
    inn.record(BallEvent(B, A, BOWLER_1))  # scorer swaps ends manually
    assert inn.batters[B].balls == 1


def test_striker_and_non_striker_must_differ() -> None:
    inn, _ = make()
    with pytest.raises(IllegalEventError, match="different"):
        inn.record(BallEvent(A, A, BOWLER_1))


def test_bowler_cannot_be_batting() -> None:
    inn, _ = make()
    with pytest.raises(IllegalEventError, match="bowler"):
        inn.record(BallEvent(A, B, A))

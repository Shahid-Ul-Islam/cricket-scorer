import pytest
from scoring_helpers import BOWLER_1, BOWLER_2, A, B, C, D, make

from cricket_scorer.engine import BallEvent, DismissalType, ExtraType, IllegalEventError

BOWLED = DismissalType.BOWLED
CAUGHT = DismissalType.CAUGHT
LBW = DismissalType.LBW
RUN_OUT = DismissalType.RUN_OUT
STUMPED = DismissalType.STUMPED
HIT_WICKET = DismissalType.HIT_WICKET
RETIRED_HURT = DismissalType.RETIRED_HURT
RETIRED_OUT = DismissalType.RETIRED_OUT
FIELDER = 107


@pytest.mark.parametrize("how", [BOWLED, CAUGHT, LBW, STUMPED, HIT_WICKET])
def test_bowler_credited_dismissals(how: DismissalType) -> None:
    inn, s = make()
    s.balls(4)
    fielder = FIELDER if how in (CAUGHT, STUMPED) else None
    s.ball(0, dismissal=how, fielder=fielder)
    assert inn.wickets == 1
    assert inn.bowlers[BOWLER_1].wickets == 1
    a = inn.batters[A]
    assert a.dismissal is how and a.is_out and a.bowler == BOWLER_1 and a.fielder == fielder
    assert a.balls == 2
    assert inn.striker is None and inn.non_striker == B
    assert inn.fall_of_wickets[0].runs == 4
    assert inn.fall_of_wickets[0].overs == "0.2"
    assert inn.fall_of_wickets[0].player == A


def test_new_batter_fills_the_vacant_end() -> None:
    inn, s = make()
    s.ball(0, dismissal=BOWLED)
    s.ball(1)  # helper brings in C as striker
    assert inn.batters[C].balls == 1
    assert (inn.striker, inn.non_striker) == (B, C)


def test_dismissed_batter_cannot_return() -> None:
    inn, s = make()
    s.ball(0, dismissal=BOWLED)
    with pytest.raises(IllegalEventError, match="cannot bat again"):
        inn.record(BallEvent(A, B, BOWLER_1))


def test_caught_off_last_ball_new_batter_at_non_strikers_end() -> None:
    inn, s = make()
    s.balls(0, 0, 0, 0, 0)
    s.ball(0, dismissal=CAUGHT, fielder=FIELDER)
    assert inn.overs == "1.0"
    assert (inn.striker, inn.non_striker) == (B, None)


class TestRunOut:
    def test_runs_completed_count_and_bowler_not_credited(self) -> None:
        inn, s = make()
        s.ball(1, dismissal=RUN_OUT, dismissed=B, fielder=FIELDER)
        assert inn.runs == 1 and inn.batters[A].runs == 1
        assert inn.wickets == 1 and inn.bowlers[BOWLER_1].wickets == 0
        assert inn.batters[B].dismissal is RUN_OUT and inn.batters[B].bowler is None
        # One run completed, so A reached the non-striker's end and B was run
        # out at the striker's end, which the new batter fills.
        assert (inn.striker, inn.non_striker) == (None, A)

    def test_non_striker_run_out_without_runs(self) -> None:
        inn, s = make()
        s.ball(0, dismissal=RUN_OUT, dismissed=B)
        assert (inn.striker, inn.non_striker) == (A, None)

    def test_run_out_off_a_wide(self) -> None:
        inn, s = make()
        s.ball(1, extra=ExtraType.WIDE, dismissal=RUN_OUT, dismissed=A)
        assert inn.runs == 2 and inn.wickets == 1 and inn.legal_balls == 0

    def test_run_out_on_free_hit_allowed(self) -> None:
        inn, s = make()
        s.ball(0, extra=ExtraType.NO_BALL)
        s.ball(0, dismissal=RUN_OUT)
        assert inn.wickets == 1


def test_stumped_off_a_wide() -> None:
    inn, s = make()
    s.ball(0, extra=ExtraType.WIDE, dismissal=STUMPED, fielder=FIELDER)
    assert inn.runs == 1 and inn.wickets == 1
    assert inn.bowlers[BOWLER_1].wickets == 1
    assert inn.legal_balls == 0


@pytest.mark.parametrize(
    ("extra", "how"),
    [
        (ExtraType.NO_BALL, BOWLED),
        (ExtraType.NO_BALL, CAUGHT),
        (ExtraType.NO_BALL, STUMPED),
        (ExtraType.WIDE, BOWLED),
        (ExtraType.WIDE, LBW),
        (ExtraType.BYE, BOWLED),
        (ExtraType.LEG_BYE, LBW),
    ],
)
def test_impossible_dismissals_off_extras(extra: ExtraType, how: DismissalType) -> None:
    _, s = make()
    runs = 1 if extra in (ExtraType.BYE, ExtraType.LEG_BYE) else 0
    with pytest.raises(IllegalEventError):
        s.ball(runs, extra=extra, dismissal=how)


@pytest.mark.parametrize("how", [BOWLED, CAUGHT, LBW, STUMPED, HIT_WICKET])
def test_only_run_out_on_free_hit(how: DismissalType) -> None:
    inn, s = make()
    s.ball(0, extra=ExtraType.NO_BALL)
    with pytest.raises(IllegalEventError, match="free hit"):
        s.ball(0, dismissal=how)
    assert inn.wickets == 0


def test_only_striker_can_be_bowled() -> None:
    _, s = make()
    with pytest.raises(IllegalEventError, match="only the striker"):
        s.ball(0, dismissal=BOWLED, dismissed=B)


def test_no_runs_on_caught() -> None:
    _, s = make()
    with pytest.raises(IllegalEventError, match="no runs"):
        s.ball(1, dismissal=CAUGHT)


def test_no_fielder_for_bowled() -> None:
    _, s = make()
    with pytest.raises(IllegalEventError, match="no fielder"):
        s.ball(0, dismissal=BOWLED, fielder=FIELDER)


def test_dismissed_must_be_batting() -> None:
    _, s = make()
    with pytest.raises(IllegalEventError, match="one of the batters"):
        s.ball(0, dismissal=RUN_OUT, dismissed=D)


def test_fielder_without_dismissal_rejected() -> None:
    _, s = make()
    with pytest.raises(IllegalEventError, match="without a dismissal"):
        s.ball(0, fielder=FIELDER)


def test_partnership_resets_after_wicket() -> None:
    inn, s = make()
    s.balls(4, 1)
    s.ball(0, dismissal=BOWLED)
    assert (inn.partnership.runs, inn.partnership.balls) == (0, 0)
    s.ball(2)
    assert (inn.partnership.runs, inn.partnership.balls) == (2, 1)


def test_all_out_ends_innings() -> None:
    inn, s = make(overs=10, players_per_side=3)
    s.ball(0, dismissal=BOWLED)
    s.ball(0, dismissal=BOWLED)
    assert inn.all_out and inn.is_complete
    with pytest.raises(IllegalEventError, match="complete"):
        s.ball(0)


def test_wicket_label() -> None:
    inn, s = make()
    s.ball(0, dismissal=BOWLED)
    s.ball(2, dismissal=RUN_OUT)
    assert [a.label for a in inn.this_over] == ["W", "2+W"]


class TestRetirement:
    def test_retired_hurt_is_not_a_wicket_and_not_a_ball(self) -> None:
        inn, s = make()
        s.balls(4, 0)
        s.ball(0, dismissal=RETIRED_HURT)
        assert inn.wickets == 0
        assert inn.legal_balls == 2
        assert inn.fall_of_wickets == []
        assert inn.batters[A].dismissal is RETIRED_HURT and not inn.batters[A].is_out
        assert inn.striker is None
        assert inn.this_over[-1].label == "0"  # retirements are not deliveries

    def test_retired_hurt_batter_can_resume(self) -> None:
        inn, s = make()
        s.ball(4)
        s.ball(0, dismissal=RETIRED_HURT)  # A retires
        s.ball(0, dismissal=BOWLED)  # C comes in and is bowled
        inn.record(BallEvent(A, B, BOWLER_1, runs=2))
        assert inn.batters[A].runs == 6 and inn.batters[A].dismissal is None
        assert list(inn.batters) == [A, B, C]  # batting order unchanged

    def test_retired_out_is_a_wicket_not_credited_to_bowler(self) -> None:
        inn, s = make()
        s.ball(0, dismissal=RETIRED_OUT, dismissed=B)
        assert inn.wickets == 1 and inn.fall_of_wickets[0].player == B
        assert inn.bowlers == {}
        assert inn.batters[B].is_out

    def test_retirement_does_not_need_bowler_for_new_over(self) -> None:
        inn, s = make()
        s.balls(0, 0, 0, 0, 0, 0)
        # Retire between overs naming the previous over's bowler: not a delivery.
        inn.record(BallEvent(B, A, BOWLER_1, dismissal=RETIRED_HURT))
        s.ball(0, bowler=BOWLER_2)
        assert inn.legal_balls == 7

    def test_retirement_cannot_carry_runs(self) -> None:
        _, s = make()
        with pytest.raises(IllegalEventError, match="not a delivery"):
            s.ball(1, dismissal=RETIRED_HURT)

    def test_retirement_keeps_free_hit(self) -> None:
        inn, s = make()
        s.ball(0, extra=ExtraType.NO_BALL)
        s.ball(0, dismissal=RETIRED_HURT)
        assert inn.free_hit

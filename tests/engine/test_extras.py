import pytest
from scoring_helpers import BOWLER_1, A, B, make

from cricket_scorer.engine import ExtraType, IllegalEventError

WD, NB, BYE, LB = ExtraType.WIDE, ExtraType.NO_BALL, ExtraType.BYE, ExtraType.LEG_BYE


def test_wide_is_one_run_extra_and_not_a_legal_ball() -> None:
    inn, s = make()
    s.ball(0, extra=WD)
    assert inn.runs == 1
    assert inn.legal_balls == 0
    assert inn.extras[WD] == 1
    assert inn.batters[A].balls == 0
    bowler = inn.bowlers[BOWLER_1]
    assert (bowler.runs, bowler.wides, bowler.legal_balls) == (1, 1, 0)


def test_wides_and_no_balls_extend_the_over() -> None:
    inn, s = make()
    s.balls(0, 0, 0)
    s.ball(0, extra=WD)
    s.ball(0, extra=NB)
    s.balls(0, 0)
    assert inn.overs == "0.5"
    assert inn.over_in_progress
    s.ball(0)
    assert inn.overs == "1.0"
    assert [a.label for a in inn.this_over] == ["0", "0", "0", "1wd", "nb", "0", "0", "0"]


def test_wide_runs_run_rotate_strike() -> None:
    inn, s = make()
    s.ball(1, extra=WD)  # one run taken on a wide: 2 wides total
    assert inn.runs == 2 and inn.extras[WD] == 2
    assert inn.striker == B


def test_wide_boundary() -> None:
    inn, s = make()
    s.ball(4, extra=WD)
    assert inn.runs == 5 and inn.extras[WD] == 5
    assert inn.striker == A
    assert [a.label for a in inn.this_over] == ["5wd"]


def test_no_ball_runs_off_bat_go_to_batter() -> None:
    inn, s = make()
    s.ball(4, extra=NB)
    assert inn.runs == 5
    assert inn.extras[NB] == 1
    assert inn.batters[A].runs == 4 and inn.batters[A].fours == 1
    assert inn.batters[A].balls == 1  # a no-ball counts as a ball faced
    assert inn.bowlers[BOWLER_1].runs == 5
    assert inn.bowlers[BOWLER_1].no_balls == 1
    assert inn.legal_balls == 0


def test_no_ball_odd_runs_rotate_strike() -> None:
    inn, s = make()
    s.ball(1, extra=NB)
    assert inn.striker == B


@pytest.mark.parametrize("extra", [BYE, LB])
def test_byes_count_as_legal_ball_but_not_to_bowler_or_batter(extra: ExtraType) -> None:
    inn, s = make()
    s.ball(1, extra=extra)
    assert inn.runs == 1 and inn.extras[extra] == 1
    assert inn.legal_balls == 1
    assert inn.batters[A].runs == 0 and inn.batters[A].balls == 1
    assert inn.bowlers[BOWLER_1].runs == 0
    assert inn.bowlers[BOWLER_1].dots == 1
    assert inn.striker == B


def test_byes_do_not_spoil_a_maiden() -> None:
    inn, s = make()
    s.ball(4, extra=BYE)
    s.balls(0, 0, 0, 0, 0)
    assert inn.bowlers[BOWLER_1].maidens == 1


def test_wide_spoils_a_maiden() -> None:
    inn, s = make()
    s.ball(0, extra=WD)
    s.balls(0, 0, 0, 0, 0, 0)
    assert inn.bowlers[BOWLER_1].maidens == 0


def test_byes_need_at_least_one_run() -> None:
    _, s = make()
    with pytest.raises(IllegalEventError, match="at least one"):
        s.ball(0, extra=BYE)


def test_runs_out_of_range() -> None:
    _, s = make()
    with pytest.raises(IllegalEventError, match="between"):
        s.ball(8)
    with pytest.raises(IllegalEventError, match="between"):
        s.ball(-1)


def test_total_extras() -> None:
    inn, s = make()
    s.ball(0, extra=WD)
    s.ball(0, extra=NB)
    s.ball(2, extra=BYE)
    s.ball(1, extra=LB)
    assert inn.total_extras == 5
    assert inn.runs == 5


class TestFreeHit:
    def test_delivery_after_no_ball_is_free_hit(self) -> None:
        inn, s = make()
        assert not inn.free_hit
        s.ball(0, extra=NB)
        assert inn.free_hit
        s.ball(1)
        assert inn.applied[-1].free_hit
        assert not inn.free_hit

    def test_free_hit_carries_over_a_wide(self) -> None:
        inn, s = make()
        s.ball(0, extra=NB)
        s.ball(0, extra=WD)
        assert inn.free_hit

    def test_free_hit_renewed_by_another_no_ball(self) -> None:
        inn, s = make()
        s.ball(0, extra=NB)
        s.ball(0, extra=NB)
        assert inn.free_hit

    def test_free_hit_survives_end_of_over(self) -> None:
        inn, s = make()
        s.balls(0, 0, 0, 0, 0)
        s.ball(0, extra=NB)
        s.ball(0)  # sixth legal ball, the free hit
        assert inn.applied[-1].free_hit
        assert inn.overs == "1.0"

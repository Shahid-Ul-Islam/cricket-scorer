from cricket_scorer.engine.types import BallEvent, DismissalType, ExtraType, format_overs


def ball(**kw) -> BallEvent:
    return BallEvent(striker=1, non_striker=2, bowler=10, **kw)


def test_format_overs() -> None:
    assert format_overs(0) == "0.0"
    assert format_overs(6) == "1.0"
    assert format_overs(15) == "2.3"


def test_plain_runs_are_bat_runs() -> None:
    b = ball(runs=4)
    assert (b.total_runs, b.bat_runs, b.extra_runs, b.bowler_runs) == (4, 4, 0, 4)
    assert b.is_legal and b.faced_by_striker


def test_wide_adds_penalty_and_is_not_legal() -> None:
    b = ball(runs=2, extra=ExtraType.WIDE)
    assert (b.total_runs, b.bat_runs, b.extra_runs, b.bowler_runs) == (3, 0, 3, 3)
    assert not b.is_legal and not b.faced_by_striker


def test_no_ball_runs_off_bat_count_to_batter() -> None:
    b = ball(runs=4, extra=ExtraType.NO_BALL)
    assert (b.total_runs, b.bat_runs, b.extra_runs, b.bowler_runs) == (5, 4, 1, 5)
    assert not b.is_legal and b.faced_by_striker


def test_byes_not_charged_to_bowler() -> None:
    for extra in (ExtraType.BYE, ExtraType.LEG_BYE):
        b = ball(runs=3, extra=extra)
        assert (b.total_runs, b.bat_runs, b.extra_runs, b.bowler_runs) == (3, 0, 3, 0)
        assert b.is_legal


def test_dismissal_properties() -> None:
    assert DismissalType.CAUGHT.credited_to_bowler
    assert not DismissalType.RUN_OUT.credited_to_bowler
    assert not DismissalType.RETIRED_OUT.credited_to_bowler
    assert DismissalType.RETIRED_OUT.counts_as_wicket
    assert not DismissalType.RETIRED_HURT.counts_as_wicket


def test_retirement_is_not_a_delivery() -> None:
    b = ball(dismissal=DismissalType.RETIRED_HURT)
    assert not b.is_delivery and not b.is_legal and b.out_player == 1

import pytest
from sqlalchemy.orm import Session

from cricket_scorer.engine import BallEvent, DismissalType, ExtraType, IllegalEventError
from cricket_scorer.models import Ball, MatchStatus, Over, TossDecision
from cricket_scorer.services import ServiceError, matches, teams
from factories import bowl_over, make_match


class TestTeams:
    def test_create_team_and_players(self, session: Session) -> None:
        team = teams.create_team(session, "  Riverside   CC ")
        teams.add_player(session, team.id, "Zed")
        teams.add_player(session, team.id, "Amir")
        assert team.name == "Riverside CC"
        session.expire_all()  # order_by applies when the collection is loaded
        assert [p.name for p in teams.get_team(session, team.id).players] == ["Amir", "Zed"]

    def test_duplicate_names_rejected(self, session: Session) -> None:
        team = teams.create_team(session, "Riverside")
        with pytest.raises(ServiceError, match="already exists"):
            teams.create_team(session, "riverside")
        teams.add_player(session, team.id, "Amir")
        with pytest.raises(ServiceError, match="already has"):
            teams.add_player(session, team.id, "AMIR")

    def test_empty_name_rejected(self, session: Session) -> None:
        with pytest.raises(ServiceError, match="empty"):
            teams.create_team(session, "   ")


class TestCreateMatch:
    def test_toss_starts_first_innings(self, session: Session) -> None:
        fx = make_match(session, toss=None)
        assert fx.match.status is MatchStatus.SCHEDULED
        matches.record_toss(session, fx.match, fx.away.id, TossDecision.BOWL)
        assert fx.match.status is MatchStatus.IN_PROGRESS
        innings = matches.current_innings(fx.match)
        assert innings is not None and innings.number == 1
        assert innings.batting_team is fx.home and innings.bowling_team is fx.away

    def test_toss_only_once(self, session: Session) -> None:
        fx = make_match(session)
        with pytest.raises(ServiceError, match="already"):
            matches.record_toss(session, fx.match, fx.home.id, TossDecision.BAT)

    def test_validation(self, session: Session) -> None:
        team = teams.create_team(session, "Solo")
        with pytest.raises(ServiceError, match="itself"):
            matches.create_match(
                session, home_team_id=team.id, away_team_id=team.id, overs_per_side=20
            )


class TestRecordBall:
    def test_ball_is_stored_with_its_over(self, session: Session) -> None:
        fx = make_match(session)
        bowl_over(fx, fx.a(1), [1, 4])
        innings = matches.current_innings(fx.match)
        assert innings is not None
        assert [b.runs for b in innings.balls] == [1, 4]
        assert [b.seq for b in innings.balls] == [0, 1]
        assert len(innings.overs) == 1 and innings.overs[0].bowler_id == fx.a(1)
        state = matches.innings_state(fx.match, innings)
        assert state.runs == 5

    def test_illegal_event_not_stored(self, session: Session) -> None:
        fx = make_match(session)
        bowl_over(fx, fx.a(1), [0] * 6)
        with pytest.raises(IllegalEventError, match="consecutive"):
            matches.record_ball(session, fx.match, BallEvent(fx.h(2), fx.h(1), fx.a(1)))
        assert session.query(Ball).count() == 6

    def test_players_must_be_from_the_right_teams(self, session: Session) -> None:
        fx = make_match(session)
        with pytest.raises(ServiceError, match="batters"):
            matches.record_ball(session, fx.match, BallEvent(fx.a(1), fx.h(2), fx.a(3)))
        with pytest.raises(ServiceError, match="bowler"):
            matches.record_ball(session, fx.match, BallEvent(fx.h(1), fx.h(2), fx.h(3)))
        with pytest.raises(ServiceError, match="fielder"):
            matches.record_ball(
                session,
                fx.match,
                BallEvent(
                    fx.h(1),
                    fx.h(2),
                    fx.a(1),
                    dismissal=DismissalType.CAUGHT,
                    fielder=fx.h(5),
                ),
            )

    def test_retirement_has_no_over(self, session: Session) -> None:
        fx = make_match(session)
        bowl_over(fx, fx.a(1), [1])
        ev = BallEvent(fx.h(2), fx.h(1), fx.a(1), dismissal=DismissalType.RETIRED_HURT)
        matches.record_ball(session, fx.match, ev)
        innings = matches.current_innings(fx.match)
        assert innings is not None
        assert innings.balls[-1].over is None


def play_first_innings(fx, runs_per_ball: int = 1) -> None:
    bowl_over(fx, fx.a(1), [runs_per_ball] * 6)
    bowl_over(fx, fx.a(2), [runs_per_ball] * 6)


class TestMatchFlow:
    def test_second_innings_starts_when_first_completes(self, session: Session) -> None:
        fx = make_match(session, overs=2)
        play_first_innings(fx)
        innings = matches.current_innings(fx.match)
        assert innings is not None and innings.number == 2
        assert innings.batting_team is fx.away
        assert matches.target_for(fx.match, innings) == 13

    def test_chasing_side_wins_by_wickets(self, session: Session) -> None:
        fx = make_match(session, overs=2)
        play_first_innings(fx)  # 12
        bowl_over(fx, fx.h(1), [6, 6, 1], batting="away")
        assert fx.match.status is MatchStatus.COMPLETED
        assert fx.match.winner is fx.away
        assert fx.match.result == "Away CC won by 10 wickets"

    def test_defending_side_wins_by_runs(self, session: Session) -> None:
        fx = make_match(session, overs=2)
        play_first_innings(fx)  # 12
        bowl_over(fx, fx.h(1), [1] * 6, batting="away")
        bowl_over(fx, fx.h(2), [0] * 6, batting="away")
        assert fx.match.winner is fx.home
        assert fx.match.result == "Home CC won by 6 runs"

    def test_tie(self, session: Session) -> None:
        fx = make_match(session, overs=2)
        play_first_innings(fx)  # 12
        bowl_over(fx, fx.h(1), [2] * 6, batting="away")
        bowl_over(fx, fx.h(2), [0] * 6, batting="away")
        assert fx.match.winner is None and fx.match.result == "Match tied"

    def test_close_innings_early(self, session: Session) -> None:
        fx = make_match(session, overs=5)
        bowl_over(fx, fx.a(1), [4])
        matches.close_innings(session, fx.match)
        innings = matches.current_innings(fx.match)
        assert innings is not None and innings.number == 2
        assert matches.target_for(fx.match, innings) == 5


class TestUndo:
    def test_undo_removes_ball_and_empty_over(self, session: Session) -> None:
        fx = make_match(session)
        bowl_over(fx, fx.a(1), [0] * 6)
        bowl_over(fx, fx.a(2), [4])
        event = matches.undo_last_ball(session, fx.match)
        assert event is not None and event.runs == 4
        assert session.query(Over).count() == 1
        assert session.query(Ball).count() == 6

    def test_undo_keeps_over_with_remaining_balls(self, session: Session) -> None:
        fx = make_match(session)
        bowl_over(fx, fx.a(1), [1, 2])
        matches.undo_last_ball(session, fx.match)
        assert session.query(Over).count() == 1

    def test_undo_across_innings_boundary(self, session: Session) -> None:
        fx = make_match(session, overs=2)
        play_first_innings(fx)
        assert len(fx.match.innings) == 2
        matches.undo_last_ball(session, fx.match)
        assert len(fx.match.innings) == 1
        innings = matches.current_innings(fx.match)
        assert innings is not None
        assert matches.innings_state(fx.match, innings).overs == "1.5"

    def test_undo_reopens_completed_match(self, session: Session) -> None:
        fx = make_match(session, overs=2)
        play_first_innings(fx)
        bowl_over(fx, fx.h(1), [6, 6, 1], batting="away")
        matches.undo_last_ball(session, fx.match)
        assert fx.match.status is MatchStatus.IN_PROGRESS
        assert fx.match.result is None and fx.match.winner_id is None

    def test_undo_reopens_closed_innings(self, session: Session) -> None:
        fx = make_match(session, overs=5)
        bowl_over(fx, fx.a(1), [4])
        matches.close_innings(session, fx.match)
        assert matches.undo_last_ball(session, fx.match) is None
        innings = matches.current_innings(fx.match)
        assert innings is not None and innings.number == 1 and not innings.closed
        assert matches.innings_state(fx.match, innings).runs == 4

    def test_nothing_to_undo(self, session: Session) -> None:
        fx = make_match(session)
        with pytest.raises(ServiceError, match="nothing"):
            matches.undo_last_ball(session, fx.match)

    def test_undo_persists(self, session_factory) -> None:
        with session_factory() as s:
            fx = make_match(s)
            bowl_over(fx, fx.a(1), [1, 2, 3])
            matches.undo_last_ball(s, fx.match)
            s.commit()
            match_id = fx.match.id
        with session_factory() as s:
            match = matches.get_match(s, match_id)
            innings = matches.current_innings(match)
            assert innings is not None
            assert [b.runs for b in innings.balls] == [1, 2]


def test_extras_survive_round_trip(session: Session) -> None:
    fx = make_match(session)
    ev = BallEvent(fx.h(1), fx.h(2), fx.a(1), runs=2, extra=ExtraType.NO_BALL)
    matches.record_ball(session, fx.match, ev)
    session.expire_all()
    innings = matches.current_innings(fx.match)
    assert innings is not None
    state = matches.innings_state(fx.match, innings)
    assert state.runs == 3 and state.free_hit

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cricket_scorer.engine import BallEvent, DismissalType, ExtraType
from cricket_scorer.models import Ball, Innings, Match, MatchStatus, Over, Player, Team


def test_team_players_and_match_round_trip(session: Session) -> None:
    home = Team(name="Home CC", players=[Player(name="Ali"), Player(name="Ben")])
    away = Team(name="Away CC", players=[Player(name="Cal")])
    match = Match(home_team=home, away_team=away, overs_per_side=20)
    session.add(match)
    session.commit()

    loaded = session.get(Match, match.id)
    assert loaded is not None
    assert loaded.title == "Home CC v Away CC"
    assert loaded.status is MatchStatus.SCHEDULED
    assert [p.name for p in loaded.home_team.players] == ["Ali", "Ben"]
    assert loaded.other_team(home.id) is away


def test_player_names_unique_within_team(session: Session) -> None:
    session.add(Team(name="T", players=[Player(name="Ali"), Player(name="Ali")]))
    with pytest.raises(IntegrityError):
        session.commit()


def test_ball_round_trips_to_engine_event(session: Session) -> None:
    home = Team(name="H", players=[Player(name="a"), Player(name="b")])
    away = Team(name="A", players=[Player(name="c"), Player(name="d")])
    match = Match(home_team=home, away_team=away, overs_per_side=5)
    innings = Innings(match=match, number=1, batting_team=home, bowling_team=away)
    session.add(innings)
    session.flush()
    a, b = home.players
    c, d = away.players
    over = Over(innings=innings, number=0, bowler_id=c.id)
    session.add(over)
    innings.balls.append(
        Ball(
            over=over,
            seq=0,
            striker_id=a.id,
            non_striker_id=b.id,
            bowler_id=c.id,
            runs=1,
            extra=ExtraType.WIDE,
            dismissal=DismissalType.STUMPED,
            fielder_id=d.id,
        )
    )
    session.commit()
    session.expire_all()

    loaded = session.get(Innings, innings.id)
    assert loaded is not None
    assert loaded.events() == [
        BallEvent(
            a.id,
            b.id,
            c.id,
            runs=1,
            extra=ExtraType.WIDE,
            dismissal=DismissalType.STUMPED,
            fielder=d.id,
        )
    ]
    assert loaded.balls[0].extra is ExtraType.WIDE
    assert loaded.overs[0].balls[0] is loaded.balls[0]

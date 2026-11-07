"""Builders for database-backed tests."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from cricket_scorer.engine import BallEvent
from cricket_scorer.models import Match, Player, Team, TossDecision
from cricket_scorer.services import matches, teams


@dataclass
class Fixture:
    session: Session
    home: Team
    away: Team
    match: Match

    def p(self, team: Team, n: int) -> int:
        """Id of the n-th (1-based) player of ``team`` in creation order."""
        return sorted(team.players, key=lambda pl: pl.id)[n - 1].id

    def h(self, n: int) -> int:
        return self.p(self.home, n)

    def a(self, n: int) -> int:
        return self.p(self.away, n)


def make_match(
    session: Session,
    *,
    overs: int = 2,
    players: int = 11,
    toss: TossDecision | None = TossDecision.BAT,
    **kw,
) -> Fixture:
    home = teams.create_team(session, "Home CC")
    away = teams.create_team(session, "Away CC")
    for team, prefix in ((home, "H"), (away, "A")):
        for i in range(1, players + 1):
            teams.add_player(session, team.id, f"{prefix}{i}")
    match = matches.create_match(
        session,
        home_team_id=home.id,
        away_team_id=away.id,
        overs_per_side=overs,
        players_per_side=players,
        **kw,
    )
    if toss is not None:
        matches.record_toss(session, match, home.id, toss)  # home bats first
    return Fixture(session, home, away, match)


def bowl_over(fx: Fixture, bowler: int, runs: list[int], batting: str = "home") -> None:
    """Record plain deliveries, letting the engine track strike."""
    side = fx.h if batting == "home" else fx.a
    for r in runs:
        innings = matches.current_innings(fx.match)
        assert innings is not None
        state = matches.innings_state(fx.match, innings)
        striker = state.striker or side(1)
        non_striker = state.non_striker or side(2)
        matches.record_ball(fx.session, fx.match, BallEvent(striker, non_striker, bowler, runs=r))


def player_name(session: Session, player_id: int) -> str:
    player = session.get(Player, player_id)
    assert player is not None
    return player.name

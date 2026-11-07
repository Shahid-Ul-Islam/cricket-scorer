"""Match lifecycle: create, toss, record balls, undo, close innings, result."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from cricket_scorer.engine import BallEvent, InningsConfig
from cricket_scorer.engine.innings import Innings as InningsState
from cricket_scorer.models import (
    Ball,
    Innings,
    Match,
    MatchStatus,
    Over,
    TossDecision,
)
from cricket_scorer.services import ServiceError
from cricket_scorer.services.teams import get_team


def list_matches(session: Session) -> list[Match]:
    return list(session.scalars(select(Match).order_by(Match.date.desc(), Match.id.desc())))


def get_match(session: Session, match_id: int) -> Match:
    match = session.get(Match, match_id)
    if match is None:
        raise ServiceError(f"match {match_id} not found")
    return match


def create_match(
    session: Session,
    *,
    home_team_id: int,
    away_team_id: int,
    overs_per_side: int,
    players_per_side: int = 11,
    max_overs_per_bowler: int | None = None,
    date: dt.date | None = None,
    venue: str | None = None,
) -> Match:
    if home_team_id == away_team_id:
        raise ServiceError("a team cannot play itself")
    if not 1 <= overs_per_side <= 100:
        raise ServiceError("overs per side must be between 1 and 100")
    if not 2 <= players_per_side <= 11:
        raise ServiceError("players per side must be between 2 and 11")
    if max_overs_per_bowler is not None and max_overs_per_bowler < 1:
        raise ServiceError("max overs per bowler must be at least 1")
    match = Match(
        home_team=get_team(session, home_team_id),
        away_team=get_team(session, away_team_id),
        overs_per_side=overs_per_side,
        players_per_side=players_per_side,
        max_overs_per_bowler=max_overs_per_bowler,
        date=date or dt.date.today(),
        venue=(venue or "").strip() or None,
    )
    session.add(match)
    session.flush()
    return match


def record_toss(session: Session, match: Match, winner_id: int, decision: TossDecision) -> Innings:
    """Record the toss and start the first innings."""
    if match.status is not MatchStatus.SCHEDULED:
        raise ServiceError("the toss has already been recorded")
    if winner_id not in (match.home_team_id, match.away_team_id):
        raise ServiceError("the toss winner must be one of the two teams")
    match.toss_winner_id = winner_id
    match.toss_decision = decision
    batting_id = winner_id if decision is TossDecision.BAT else match.other_team(winner_id).id
    match.status = MatchStatus.IN_PROGRESS
    innings = _start_innings(session, match, number=1, batting_team_id=batting_id)
    session.flush()
    return innings


def _start_innings(session: Session, match: Match, *, number: int, batting_team_id: int) -> Innings:
    innings = Innings(
        number=number,
        batting_team_id=batting_team_id,
        bowling_team_id=match.other_team(batting_team_id).id,
    )
    match.innings.append(innings)
    session.flush()
    return innings


# ----------------------------------------------------------------- state


def current_innings(match: Match) -> Innings | None:
    if match.status is not MatchStatus.IN_PROGRESS or not match.innings:
        return None
    return match.innings[-1]


def target_for(match: Match, innings: Innings) -> int | None:
    if innings.number != 2:
        return None
    return innings_state(match, match.innings[0]).runs + 1


def innings_state(match: Match, innings: Innings) -> InningsState:
    """Replay an innings' stored events through the engine."""
    config = InningsConfig(
        overs=match.overs_per_side,
        players_per_side=match.players_per_side,
        target=target_for(match, innings),
        max_overs_per_bowler=match.max_overs_per_bowler,
    )
    state = InningsState(config, innings.events())
    if innings.closed:
        state.close()
    return state


@dataclass(frozen=True)
class InningsView:
    innings: Innings
    state: InningsState


def match_innings(match: Match) -> list[InningsView]:
    return [InningsView(i, innings_state(match, i)) for i in match.innings]


# -------------------------------------------------------------- scoring


def record_ball(session: Session, match: Match, event: BallEvent) -> InningsState:
    """Validate ``event`` against the current innings, store it and advance the
    match if the innings is now complete. Raises ``ServiceError`` or
    ``IllegalEventError``."""
    innings = current_innings(match)
    if innings is None:
        raise ServiceError("the match is not in progress")
    _check_teams(innings, event)

    state = innings_state(match, innings)
    state.record(event)
    applied = state.applied[-1]

    over = None
    if event.is_delivery:
        over = next((o for o in innings.overs if o.number == applied.over_index), None)
        if over is None:
            over = Over(innings=innings, number=applied.over_index, bowler_id=event.bowler)
            session.add(over)
    innings.balls.append(
        Ball(
            over=over,
            seq=len(innings.balls),
            striker_id=event.striker,
            non_striker_id=event.non_striker,
            bowler_id=event.bowler,
            runs=event.runs,
            extra=event.extra,
            dismissal=event.dismissal,
            dismissed_id=event.dismissed,
            fielder_id=event.fielder,
        )
    )
    session.flush()
    if state.is_complete:
        _advance(session, match, innings, state)
    return state


def _check_teams(innings: Innings, event: BallEvent) -> None:
    batting = {p.id for p in innings.batting_team.players}
    bowling = {p.id for p in innings.bowling_team.players}
    if event.striker not in batting or event.non_striker not in batting:
        raise ServiceError(f"batters must be from {innings.batting_team.name}")
    if event.bowler not in bowling:
        raise ServiceError(f"the bowler must be from {innings.bowling_team.name}")
    if event.fielder is not None and event.fielder not in bowling:
        raise ServiceError(f"the fielder must be from {innings.bowling_team.name}")


def close_innings(session: Session, match: Match) -> None:
    """End the current innings early (e.g. no fit batters left)."""
    innings = current_innings(match)
    if innings is None:
        raise ServiceError("the match is not in progress")
    innings.closed = True
    session.flush()
    _advance(session, match, innings, innings_state(match, innings))


def _advance(session: Session, match: Match, innings: Innings, state: InningsState) -> None:
    if innings.number == 1:
        _start_innings(session, match, number=2, batting_team_id=innings.bowling_team_id)
    else:
        _finish(match, state)
    session.flush()


def _finish(match: Match, chase: InningsState) -> None:
    first, second = match.innings
    target = chase.config.target
    assert target is not None
    match.status = MatchStatus.COMPLETED
    if chase.runs >= target:
        winner = second.batting_team
        margin = chase.config.max_wickets - chase.wickets
        match.winner_id = winner.id
        match.result = f"{winner.name} won by {margin} wicket{'s' if margin != 1 else ''}"
    elif chase.runs == target - 1:
        match.winner_id = None
        match.result = "Match tied"
    else:
        winner = first.batting_team
        margin = target - 1 - chase.runs
        match.winner_id = winner.id
        match.result = f"{winner.name} won by {margin} run{'s' if margin != 1 else ''}"


def undo_last_ball(session: Session, match: Match) -> BallEvent | None:
    """Remove the most recent event in the match, reopening a finished innings
    or match if needed. Returns the removed event, or ``None`` if the undo only
    reopened an innings that had been closed early."""
    if match.status is MatchStatus.SCHEDULED or not match.innings:
        raise ServiceError("nothing to undo")

    if match.status is MatchStatus.COMPLETED:
        match.status = MatchStatus.IN_PROGRESS
        match.winner_id = None
        match.result = None

    innings = match.innings[-1]
    if not innings.balls and innings.number == 2 and not innings.closed:
        # The second innings has not started: undo into the first innings.
        match.innings.remove(innings)
        session.flush()
        innings = match.innings[-1]

    if innings.closed:
        innings.closed = False  # undo the early close first
        session.flush()
        return None

    if not innings.balls:
        raise ServiceError("nothing to undo")
    ball = innings.balls.pop()  # delete-orphan cascade removes the row
    event = ball.to_event()
    over = ball.over
    if over is not None and not any(b.over is over for b in innings.balls):
        innings.overs.remove(over)
    session.flush()
    return event

"""Teams and players."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cricket_scorer.models import Player, Team
from cricket_scorer.services import ServiceError


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned:
        raise ServiceError("name cannot be empty")
    if len(cleaned) > 100:
        raise ServiceError("name is too long (max 100 characters)")
    return cleaned


def list_teams(session: Session) -> list[Team]:
    return list(session.scalars(select(Team).order_by(Team.name)))


def get_team(session: Session, team_id: int) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise ServiceError(f"team {team_id} not found")
    return team


def create_team(session: Session, name: str) -> Team:
    name = _clean_name(name)
    exists = session.scalar(select(Team).where(func.lower(Team.name) == name.lower()))
    if exists is not None:
        raise ServiceError(f"a team called {name!r} already exists")
    team = Team(name=name)
    session.add(team)
    session.flush()
    return team


def add_player(session: Session, team_id: int, name: str) -> Player:
    team = get_team(session, team_id)
    name = _clean_name(name)
    if any(p.name.lower() == name.lower() for p in team.players):
        raise ServiceError(f"{team.name} already has a player called {name!r}")
    player = Player(name=name, team=team)
    session.add(player)
    session.flush()
    return player


def get_player(session: Session, player_id: int) -> Player:
    player = session.get(Player, player_id)
    if player is None:
        raise ServiceError(f"player {player_id} not found")
    return player


def list_players(session: Session) -> list[Player]:
    return list(session.scalars(select(Player).order_by(Player.name)))

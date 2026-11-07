"""Match list, creation and toss."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from cricket_scorer.models import MatchStatus, TossDecision
from cricket_scorer.services import ServiceError, matches, teams
from cricket_scorer.web.deps import SessionDep, templates

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_class=HTMLResponse)
def list_matches(request: Request, session: SessionDep) -> Response:
    rows = [(m, matches.match_innings(m)) for m in matches.list_matches(session)]
    return templates.TemplateResponse(request, "matches/list.html", {"rows": rows})


def _new_form(request: Request, session: SessionDep, error: str | None, form: dict) -> Response:
    return templates.TemplateResponse(
        request,
        "matches/new.html",
        {
            "teams": teams.list_teams(session),
            "error": error,
            "form": form,
            "today": dt.date.today().isoformat(),
        },
        status_code=422 if error else 200,
    )


@router.get("/new", response_class=HTMLResponse)
def new_match(request: Request, session: SessionDep) -> Response:
    return _new_form(request, session, None, {})


def _optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


@router.post("")
def create_match(
    request: Request,
    session: SessionDep,
    home_team_id: Annotated[int, Form()],
    away_team_id: Annotated[int, Form()],
    overs_per_side: Annotated[int, Form()],
    players_per_side: Annotated[int, Form()] = 11,
    max_overs_per_bowler: Annotated[str, Form()] = "",
    date: Annotated[str, Form()] = "",
    venue: Annotated[str, Form()] = "",
) -> Response:
    form = {
        "home_team_id": home_team_id,
        "away_team_id": away_team_id,
        "overs_per_side": overs_per_side,
        "players_per_side": players_per_side,
        "max_overs_per_bowler": max_overs_per_bowler,
        "date": date,
        "venue": venue,
    }
    try:
        match = matches.create_match(
            session,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            overs_per_side=overs_per_side,
            players_per_side=players_per_side,
            max_overs_per_bowler=_optional_int(max_overs_per_bowler),
            date=dt.date.fromisoformat(date) if date else None,
            venue=venue,
        )
    except ValueError as exc:  # ServiceError, or a malformed date / number
        return _new_form(request, session, str(exc), form)
    return RedirectResponse(f"/matches/{match.id}", status_code=303)


@router.get("/{match_id}")
def match_detail(request: Request, session: SessionDep, match_id: int) -> Response:
    match = matches.get_match(session, match_id)
    match match.status:
        case MatchStatus.SCHEDULED:
            return templates.TemplateResponse(
                request, "matches/toss.html", {"match": match, "error": None}
            )
        case MatchStatus.IN_PROGRESS:
            return RedirectResponse(f"/matches/{match_id}/score", status_code=303)
        case _:
            return RedirectResponse(f"/matches/{match_id}/scorecard", status_code=303)


@router.post("/{match_id}/toss")
def record_toss(
    request: Request,
    session: SessionDep,
    match_id: int,
    winner_id: Annotated[int, Form()],
    decision: Annotated[TossDecision, Form()],
) -> Response:
    match = matches.get_match(session, match_id)
    try:
        matches.record_toss(session, match, winner_id, decision)
    except ServiceError as exc:
        return templates.TemplateResponse(
            request, "matches/toss.html", {"match": match, "error": str(exc)}, status_code=422
        )
    return RedirectResponse(f"/matches/{match_id}/score", status_code=303)

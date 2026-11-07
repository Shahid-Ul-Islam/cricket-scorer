"""Team and player management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from cricket_scorer.services import ServiceError
from cricket_scorer.services import teams as svc
from cricket_scorer.web.deps import SessionDep, is_htmx, templates

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_class=HTMLResponse)
def list_teams(request: Request, session: SessionDep, error: str | None = None) -> Response:
    return templates.TemplateResponse(
        request, "teams/list.html", {"teams": svc.list_teams(session), "error": error}
    )


@router.post("")
def create_team(request: Request, session: SessionDep, name: Annotated[str, Form()]) -> Response:
    try:
        team = svc.create_team(session, name)
    except ServiceError as exc:
        return templates.TemplateResponse(
            request,
            "teams/list.html",
            {"teams": svc.list_teams(session), "error": str(exc)},
            status_code=422,
        )
    return RedirectResponse(f"/teams/{team.id}", status_code=303)


@router.get("/{team_id}", response_class=HTMLResponse)
def team_detail(request: Request, session: SessionDep, team_id: int) -> Response:
    team = svc.get_team(session, team_id)
    return templates.TemplateResponse(request, "teams/detail.html", {"team": team})


@router.post("/{team_id}/players")
def add_player(
    request: Request, session: SessionDep, team_id: int, name: Annotated[str, Form()]
) -> Response:
    error = None
    try:
        svc.add_player(session, team_id, name)
    except ServiceError as exc:
        error = str(exc)
    team = svc.get_team(session, team_id)
    session.refresh(team)  # reload players in name order
    if is_htmx(request):
        return templates.TemplateResponse(
            request, "teams/_players.html", {"team": team, "error": error}
        )
    if error:
        return templates.TemplateResponse(
            request, "teams/detail.html", {"team": team, "error": error}, status_code=422
        )
    return RedirectResponse(f"/teams/{team_id}", status_code=303)

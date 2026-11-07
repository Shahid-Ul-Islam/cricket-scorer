"""Player statistics pages."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from cricket_scorer.services.stats import career_stats, player_stats
from cricket_scorer.web.deps import SessionDep, templates

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_class=HTMLResponse)
def list_players(request: Request, session: SessionDep) -> Response:
    rows = sorted(
        career_stats(session).values(),
        key=lambda s: (-s.batting.runs, -s.bowling.wickets, s.player.name),
    )
    return templates.TemplateResponse(request, "players/list.html", {"rows": rows})


@router.get("/{player_id}", response_class=HTMLResponse)
def player_detail(request: Request, session: SessionDep, player_id: int) -> Response:
    return templates.TemplateResponse(
        request, "players/detail.html", {"s": player_stats(session, player_id)}
    )

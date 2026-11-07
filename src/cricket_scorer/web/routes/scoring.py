"""Live ball-by-ball scoring.

Every action posts the scoring form and, for HTMX requests, gets back the
re-rendered ``#scoring`` panel.  Without JavaScript the same endpoints
redirect back to the page (or re-render it with an error).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import FormData

from cricket_scorer.engine import BallEvent, DismissalType, ExtraType, IllegalEventError
from cricket_scorer.engine.innings import Innings as InningsState
from cricket_scorer.models import Innings, Match, Player
from cricket_scorer.services import ServiceError, matches
from cricket_scorer.web.deps import SessionDep, is_htmx, templates

router = APIRouter(prefix="/matches/{match_id}", tags=["scoring"])

RUN_BUTTONS = (0, 1, 2, 3, 4, 6)
EXTRA_BUTTONS = {
    "wide": ("Wide", (0, 1, 2, 4)),
    "nb": ("No-ball (+ bat runs)", (0, 1, 2, 4, 6)),
    "bye": ("Byes", (1, 2, 3, 4)),
    "lb": ("Leg-byes", (1, 2, 3, 4)),
}
ACTION_EXTRAS = {
    "run": None,
    "wide": ExtraType.WIDE,
    "nb": ExtraType.NO_BALL,
    "bye": ExtraType.BYE,
    "lb": ExtraType.LEG_BYE,
}
DISMISSAL_LABELS = {
    DismissalType.BOWLED: "Bowled",
    DismissalType.CAUGHT: "Caught",
    DismissalType.LBW: "LBW",
    DismissalType.RUN_OUT: "Run out",
    DismissalType.STUMPED: "Stumped",
    DismissalType.HIT_WICKET: "Hit wicket",
    DismissalType.RETIRED_HURT: "Retired hurt (not out)",
    DismissalType.RETIRED_OUT: "Retired out",
}


@dataclass
class ScoringView:
    match: Match
    innings: Innings | None = None
    state: InningsState | None = None
    first_innings: InningsState | None = None
    names: dict[int, str] = field(default_factory=dict)
    striker_options: list[Player] = field(default_factory=list)
    bowler_options: list[Player] = field(default_factory=list)
    fielders: list[Player] = field(default_factory=list)
    error: str | None = None


def build_view(match: Match, error: str | None = None) -> ScoringView:
    view = ScoringView(match=match, error=error)
    view.names = {p.id: p.name for t in (match.home_team, match.away_team) for p in t.players}
    innings = matches.current_innings(match)
    if innings is None:
        return view
    state = matches.innings_state(match, innings)
    view.innings, view.state = innings, state
    if innings.number == 2:
        view.first_innings = matches.innings_state(match, match.innings[0])

    at_crease = {state.striker, state.non_striker} - {None}
    view.striker_options = [
        p
        for p in innings.batting_team.players
        if p.id in at_crease
        or p.id not in state.batters
        or state.batters[p.id].dismissal is DismissalType.RETIRED_HURT
    ]
    if state.current_bowler is not None:
        view.bowler_options = [
            p for p in innings.bowling_team.players if p.id == state.current_bowler
        ]
    else:
        cap = match.max_overs_per_bowler
        view.bowler_options = [
            p
            for p in innings.bowling_team.players
            if p.id != state.previous_over_bowler and (cap is None or state.overs_by(p.id) < cap)
        ]
    view.fielders = list(innings.bowling_team.players)
    return view


def _render(request: Request, match: Match, error: str | None = None) -> Response:
    view = build_view(match, error)
    context = {
        "v": view,
        "run_buttons": RUN_BUTTONS,
        "extra_buttons": EXTRA_BUTTONS,
        "dismissals": DISMISSAL_LABELS,
    }
    if is_htmx(request):
        return templates.TemplateResponse(request, "scoring/_panel.html", context)
    status = 422 if error else 200
    return templates.TemplateResponse(request, "scoring/page.html", context, status_code=status)


def _int(form: FormData, key: str) -> int | None:
    raw = str(form.get(key) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ServiceError(f"invalid value for {key}") from None


def parse_event(form: FormData, state: InningsState) -> BallEvent:
    striker = _int(form, "striker")
    non_striker = _int(form, "non_striker")
    bowler = _int(form, "bowler")
    if striker is None or non_striker is None:
        raise ServiceError("choose the striker and non-striker")

    action = str(form.get("action") or "")
    if action == "wicket":
        try:
            dismissal = DismissalType(str(form.get("dismissal") or ""))
        except ValueError:
            raise ServiceError("choose how the batter was out") from None
        extra_raw = str(form.get("wicket_extra") or "")
        try:
            extra = ExtraType(extra_raw) if extra_raw else None
        except ValueError:
            raise ServiceError("invalid extra for the wicket ball") from None
        dismissed = non_striker if form.get("dismissed") == "non_striker" else striker
        runs = _int(form, "wicket_runs") or 0
        fielder = _int(form, "fielder")
        if dismissal.is_retirement:
            runs, extra, fielder = 0, None, None
            bowler = bowler or state.current_bowler or state.previous_over_bowler
    else:
        kind, _, runs_raw = action.partition(":")
        if kind not in ACTION_EXTRAS or not runs_raw.isdigit():
            raise ServiceError("unknown scoring action")
        extra, runs = ACTION_EXTRAS[kind], int(runs_raw)
        dismissal = dismissed = fielder = None

    if bowler is None:
        raise ServiceError("choose the bowler")
    return BallEvent(
        striker=striker,
        non_striker=non_striker,
        bowler=bowler,
        runs=runs,
        extra=extra,
        dismissal=dismissal,
        dismissed=dismissed if dismissal is not None else None,
        fielder=fielder,
    )


def _done(request: Request, match: Match, match_id: int) -> Response:
    if is_htmx(request):
        return _render(request, match)
    return RedirectResponse(f"/matches/{match_id}/score", status_code=303)


@router.get("/score", response_class=HTMLResponse)
def score_page(request: Request, session: SessionDep, match_id: int) -> Response:
    match = matches.get_match(session, match_id)
    if matches.current_innings(match) is None and not match.innings:
        return RedirectResponse(f"/matches/{match_id}", status_code=303)  # toss first
    return _render(request, match)


@router.post("/balls")
async def record_ball(request: Request, session: SessionDep, match_id: int) -> Response:
    match = matches.get_match(session, match_id)
    form = await request.form()
    innings = matches.current_innings(match)
    try:
        if innings is None:
            raise ServiceError("the match is not in progress")
        event = parse_event(form, matches.innings_state(match, innings))
        matches.record_ball(session, match, event)
    except (ServiceError, IllegalEventError) as exc:
        session.rollback()
        return _render(request, matches.get_match(session, match_id), str(exc))
    return _done(request, match, match_id)


@router.post("/undo")
def undo(request: Request, session: SessionDep, match_id: int) -> Response:
    match = matches.get_match(session, match_id)
    try:
        matches.undo_last_ball(session, match)
    except ServiceError as exc:
        return _render(request, match, str(exc))
    return _done(request, match, match_id)


@router.post("/close")
def close_innings(request: Request, session: SessionDep, match_id: int) -> Response:
    match = matches.get_match(session, match_id)
    try:
        matches.close_innings(session, match)
    except ServiceError as exc:
        return _render(request, match, str(exc))
    return _done(request, match, match_id)

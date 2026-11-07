"""Request-scoped dependencies and template helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from cricket_scorer.engine import format_overs

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")


def _fmt_rate(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


templates.env.filters["rate"] = _fmt_rate
templates.env.filters["overs"] = format_overs


def get_session(request: Request) -> Iterator[Session]:
    """One session per request, committed if the handler succeeds."""
    session: Session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"

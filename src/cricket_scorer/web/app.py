"""Application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from cricket_scorer import __version__
from cricket_scorer.db import init_db, make_engine, make_session_factory
from cricket_scorer.services import NotFoundError
from cricket_scorer.web.deps import WEB_DIR, templates
from cricket_scorer.web.routes import teams


def create_app(database_url: str | None = None) -> FastAPI:
    engine = make_engine(database_url)
    init_db(engine)

    app = FastAPI(title="cricket-scorer", version=__version__)
    app.state.session_factory = make_session_factory(engine)
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    app.include_router(teams.router)

    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse("/teams", status_code=303)

    @app.exception_handler(NotFoundError)
    def not_found(request: Request, exc: NotFoundError) -> HTMLResponse:
        return templates.TemplateResponse(
            request, "error.html", {"message": str(exc)}, status_code=404
        )

    return app

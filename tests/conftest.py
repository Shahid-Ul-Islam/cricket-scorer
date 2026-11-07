from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cricket_scorer.db import init_db, make_engine, make_session_factory
from cricket_scorer.web.app import create_app


@pytest.fixture
def session_factory():
    engine = make_engine("sqlite://")
    init_db(engine)
    yield make_session_factory(engine)
    engine.dispose()


@pytest.fixture
def session(session_factory) -> Iterator[Session]:
    with session_factory() as s:
        yield s


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app("sqlite://")
    with TestClient(app) as c:
        yield c

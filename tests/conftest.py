from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from cricket_scorer.db import init_db, make_engine, make_session_factory


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

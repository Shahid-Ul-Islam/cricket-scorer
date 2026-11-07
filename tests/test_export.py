import json

from sqlalchemy.orm import Session

from cricket_scorer.engine import BallEvent, DismissalType, ExtraType, InningsConfig
from cricket_scorer.engine.innings import Innings
from cricket_scorer.services import matches
from cricket_scorer.services.export import match_to_dict, scorecard_markdown
from cricket_scorer.services.scorecard import build_scorecard
from factories import Fixture, bowl_over, make_match


def record(fx: Fixture, **kw) -> None:
    innings = matches.current_innings(fx.match)
    assert innings is not None
    state = matches.innings_state(fx.match, innings)
    kw.setdefault("striker", state.striker)
    kw.setdefault("non_striker", state.non_striker)
    matches.record_ball(fx.session, fx.match, BallEvent(**kw))


def sample(session: Session) -> Fixture:
    fx = make_match(session, overs=1, venue="Pitch | One")
    record(fx, striker=fx.h(1), non_striker=fx.h(2), bowler=fx.a(1), runs=4)
    record(fx, bowler=fx.a(1), extra=ExtraType.NO_BALL)
    record(fx, bowler=fx.a(1), dismissal=DismissalType.RUN_OUT, dismissed=fx.h(2), runs=1)
    return fx


def test_json_export_contains_every_ball(session: Session) -> None:
    fx = sample(session)
    data = match_to_dict(fx.match)
    json.dumps(data)  # serialisable
    assert data["schema_version"] == 1
    assert data["match"]["home_team"]["name"] == "Home CC"
    assert len(data["match"]["home_team"]["players"]) == 11
    assert data["match"]["toss_decision"] == "bat"
    (inn,) = data["innings"]
    assert inn["summary"] == {
        "runs": 6,
        "wickets": 1,
        "overs": "0.2",
        "extras": {"wide": 0, "no_ball": 1, "bye": 0, "leg_bye": 0},
    }
    assert [b["label"] for b in inn["balls"]] == ["4", "nb", "1+W"]
    assert inn["balls"][2]["free_hit"] is True
    assert inn["balls"][2]["dismissed_id"] == fx.h(2)


def test_json_export_replays_to_same_state(session: Session) -> None:
    fx = sample(session)
    record(fx, striker=fx.h(3), non_striker=fx.h(1), bowler=fx.a(1), runs=1)  # H3 comes in
    bowl_over(fx, fx.a(1), [1, 0, 0])  # finish the first innings
    data = match_to_dict(fx.match)
    inn = data["innings"][0]
    events = [
        BallEvent(
            b["striker_id"],
            b["non_striker_id"],
            b["bowler_id"],
            runs=b["runs"],
            extra=ExtraType(b["extra"]) if b["extra"] else None,
            dismissal=DismissalType(b["dismissal"]) if b["dismissal"] else None,
            dismissed=b["dismissed_id"],
            fielder=b["fielder_id"],
        )
        for b in inn["balls"]
    ]
    replayed = Innings(InningsConfig(overs=1), events)
    assert (replayed.runs, replayed.wickets, replayed.overs) == (8, 1, "1.0")


def test_markdown_scorecard(session: Session) -> None:
    fx = sample(session)
    md = scorecard_markdown(build_scorecard(fx.match))
    assert md.startswith("# Home CC v Away CC\n")
    assert md.splitlines()[2] == "2026-11-07 · Pitch | One · 1 overs per side  ".replace(
        "2026-11-07", fx.match.date.isoformat()
    )
    assert "Home CC won the toss and elected to bat" in md
    assert "## Home CC - 6/1 (0.2 ov)" in md
    # H1: 4, faced the no-ball, then ran 1 on the run-out ball.
    assert "| H1 | not out | 5 | 3 | 1 | 0 | 166.67 |" in md
    assert "| H2 | run out | 0 | 0 | 0 | 0 | - |" in md
    assert "| Extras | nb 1 | 1 |" in md
    assert "**Fall of wickets:** 1-6 (H2, 0.2 ov)" in md
    assert "| A1 | 0.2 | 0 | 6 | 0 | 18.00 | 0 | 1 |" in md
    assert md.endswith("\n") and not md.endswith("\n\n")


def test_markdown_escapes_pipes_in_table_cells(session: Session) -> None:
    fx = make_match(session, overs=1)
    fx.home.players[0].name = "Ali | Khan"
    session.flush()
    record(fx, striker=fx.home.players[0].id, non_striker=fx.h(2), bowler=fx.a(1), runs=1)
    md = scorecard_markdown(build_scorecard(fx.match))
    assert "| Ali \\| Khan |" in md

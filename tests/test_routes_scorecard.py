from fastapi.testclient import TestClient

from web_helpers import A, H, post_ball, setup_match


def test_scorecard_page(client: TestClient) -> None:
    match_id = setup_match(client)
    post_ball(client, match_id, "run:4", H[1], H[2], A[1])
    post_ball(client, match_id, "wicket", H[1], H[2], A[1], dismissal="bowled")
    r = client.get(f"/matches/{match_id}/scorecard")
    assert r.status_code == 200
    assert "Home CC - 4/1 (0.2 ov)" in r.text
    assert "b A1" in r.text
    assert "Fall of wickets:" in r.text and "1-4 (H1, 0.2 ov)" in r.text
    assert "Live scoring" in r.text


def test_scorecard_before_start(client: TestClient) -> None:
    for name in ("X", "Y"):
        client.post("/teams", data={"name": name})
    client.post("/matches", data={"home_team_id": 1, "away_team_id": 2, "overs_per_side": 5})
    r = client.get("/matches/1/scorecard")
    assert "has not started" in r.text

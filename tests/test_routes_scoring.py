from fastapi.testclient import TestClient

from web_helpers import HTMX, A, H, post_ball, setup_match


def test_score_page_renders(client: TestClient) -> None:
    match_id = setup_match(client)
    r = client.get(f"/matches/{match_id}/score")
    assert r.status_code == 200
    assert "Home CC" in r.text and "0/0" in r.text
    assert "- new batter -" in r.text


def test_score_page_before_toss_redirects(client: TestClient) -> None:
    for name in ("X", "Y"):
        client.post("/teams", data={"name": name})
    client.post("/matches", data={"home_team_id": 1, "away_team_id": 2, "overs_per_side": 5})
    r = client.get("/matches/1/score", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/matches/1"


def test_record_runs_returns_panel(client: TestClient) -> None:
    match_id = setup_match(client)
    r = post_ball(client, match_id, "run:4", H[1], H[2], A[1])
    assert r.status_code == 200
    assert r.text.lstrip().startswith('<section id="scoring">')
    assert "4/0" in r.text
    assert '<span class="ball-chip boundary">4</span>' in r.text


def test_extras_and_free_hit_shown(client: TestClient) -> None:
    match_id = setup_match(client)
    r = post_ball(client, match_id, "nb:1", H[1], H[2], A[1])
    assert "2/0" in r.text and "FREE HIT" in r.text
    assert "nb+1" in r.text


def test_illegal_ball_shows_error(client: TestClient) -> None:
    match_id = setup_match(client)
    r = post_ball(client, match_id, "run:0", H[1], H[1], A[1])
    assert r.status_code == 200
    assert 'role="alert"' in r.text and "different players" in r.text


def test_missing_bowler_is_an_error(client: TestClient) -> None:
    match_id = setup_match(client)
    r = post_ball(client, match_id, "run:1", H[1], H[2], "")
    assert "choose the bowler" in r.text


def test_unknown_action_is_an_error(client: TestClient) -> None:
    match_id = setup_match(client)
    r = post_ball(client, match_id, "run:x", H[1], H[2], A[1])
    assert "unknown scoring action" in r.text


def test_wicket_then_new_batter(client: TestClient) -> None:
    match_id = setup_match(client)
    r = post_ball(
        client,
        match_id,
        "wicket",
        H[1],
        H[2],
        A[1],
        dismissal="caught",
        dismissed="striker",
        fielder=A[5],
    )
    assert "0/1" in r.text
    r = post_ball(client, match_id, "run:1", H[3], H[2], A[1])
    assert "1/1" in r.text and "H3" in r.text


def test_run_out_of_non_striker_with_runs(client: TestClient) -> None:
    match_id = setup_match(client)
    r = post_ball(
        client,
        match_id,
        "wicket",
        H[1],
        H[2],
        A[1],
        dismissal="run_out",
        dismissed="non_striker",
        wicket_runs=1,
    )
    assert "1/1" in r.text


def test_retirement_without_bowler_uses_current(client: TestClient) -> None:
    match_id = setup_match(client)
    post_ball(client, match_id, "run:0", H[1], H[2], A[1])
    r = post_ball(client, match_id, "wicket", H[1], H[2], "", dismissal="retired_hurt")
    assert 'role="alert"' not in r.text
    assert "0/0" in r.text


def test_undo(client: TestClient) -> None:
    match_id = setup_match(client)
    post_ball(client, match_id, "run:6", H[1], H[2], A[1])
    r = client.post(f"/matches/{match_id}/undo", headers=HTMX)
    assert "0/0" in r.text and "0.0 / 2 ov" in r.text


def test_undo_with_nothing_recorded(client: TestClient) -> None:
    match_id = setup_match(client)
    r = client.post(f"/matches/{match_id}/undo", headers=HTMX)
    assert "nothing to undo" in r.text


def test_without_htmx_redirects_back(client: TestClient) -> None:
    match_id = setup_match(client)
    r = client.post(
        f"/matches/{match_id}/balls",
        data={"striker": H[1], "non_striker": H[2], "bowler": A[1], "action": "run:2"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/matches/{match_id}/score"


def play_over(client: TestClient, match_id: int, runs: int, bat: dict, bowler: int) -> None:
    for _ in range(6):
        post_ball(client, match_id, f"run:{runs}", bat[1], bat[2], bowler)


def test_full_match_to_result(client: TestClient) -> None:
    match_id = setup_match(client, overs=1)
    play_over(client, match_id, 0, H, A[1])
    r = client.get(f"/matches/{match_id}/score")
    assert "Innings break" in r.text and "need 1 to win" in r.text
    r = post_ball(client, match_id, "run:1", A[1], A[2], H[1])
    assert "Match finished" in r.text and "Away CC won by 10 wickets" in r.text
    # Match page now points at the scorecard; undo reopens the match.
    r = client.get(f"/matches/{match_id}", follow_redirects=False)
    assert r.headers["location"].endswith("/scorecard")
    r = client.post(f"/matches/{match_id}/undo", headers=HTMX)
    assert "Innings break" in r.text and "need 1 to win" in r.text


def test_close_innings(client: TestClient) -> None:
    match_id = setup_match(client, overs=5)
    post_ball(client, match_id, "run:4", H[1], H[2], A[1])
    r = client.post(f"/matches/{match_id}/close", headers=HTMX)
    assert "Innings break" in r.text and "need 5 to win" in r.text

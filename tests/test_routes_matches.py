from fastapi.testclient import TestClient


def setup_teams(client: TestClient) -> None:
    for name in ("Home CC", "Away CC"):
        client.post("/teams", data={"name": name})
    for team_id, prefix in ((1, "H"), (2, "A")):
        for i in range(1, 12):
            client.post(f"/teams/{team_id}/players", data={"name": f"{prefix}{i}"})


def create_match(client: TestClient, **overrides) -> int:
    data = {"home_team_id": 1, "away_team_id": 2, "overs_per_side": 2, "players_per_side": 11}
    data.update(overrides)
    r = client.post("/matches", data=data, follow_redirects=False)
    assert r.status_code == 303, r.text
    return int(r.headers["location"].rsplit("/", 1)[1])


def test_index_goes_to_match_list(client: TestClient) -> None:
    r = client.get("/")
    assert r.url.path == "/matches"
    assert "No matches yet" in r.text


def test_new_match_form_needs_two_teams(client: TestClient) -> None:
    r = client.get("/matches/new")
    assert "at least two teams" in r.text


def test_create_match_shows_toss_form(client: TestClient) -> None:
    setup_teams(client)
    match_id = create_match(client, venue="The Oval", max_overs_per_bowler="")
    r = client.get(f"/matches/{match_id}")
    assert "Toss" in r.text and "Home CC v Away CC" in r.text and "The Oval" in r.text


def test_create_match_validation_error(client: TestClient) -> None:
    setup_teams(client)
    r = client.post("/matches", data={"home_team_id": 1, "away_team_id": 1, "overs_per_side": 20})
    assert r.status_code == 422 and "cannot play itself" in r.text


def test_bad_date_is_a_form_error(client: TestClient) -> None:
    setup_teams(client)
    r = client.post(
        "/matches",
        data={"home_team_id": 1, "away_team_id": 2, "overs_per_side": 20, "date": "nope"},
    )
    assert r.status_code == 422


def test_toss_redirects_to_scoring(client: TestClient) -> None:
    setup_teams(client)
    match_id = create_match(client)
    r = client.post(
        f"/matches/{match_id}/toss",
        data={"winner_id": 2, "decision": "bowl"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/matches/{match_id}/score"
    r = client.get("/matches")
    assert "Live" in r.text


def test_unknown_match_404(client: TestClient) -> None:
    assert client.get("/matches/42").status_code == 404

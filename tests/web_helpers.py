"""Helpers for route tests: build a match through the HTTP API."""

from __future__ import annotations

from fastapi.testclient import TestClient

HTMX = {"HX-Request": "true"}

# Player ids: home team H1..H11 are 1..11, away team A1..A11 are 12..22.
H = {i: i for i in range(1, 12)}
A = {i: 11 + i for i in range(1, 12)}


def setup_match(client: TestClient, overs: int = 2, players: int = 11) -> int:
    for name in ("Home CC", "Away CC"):
        client.post("/teams", data={"name": name})
    for team_id, prefix in ((1, "H"), (2, "A")):
        for i in range(1, 12):
            client.post(f"/teams/{team_id}/players", data={"name": f"{prefix}{i}"})
    r = client.post(
        "/matches",
        data={
            "home_team_id": 1,
            "away_team_id": 2,
            "overs_per_side": overs,
            "players_per_side": players,
        },
        follow_redirects=False,
    )
    match_id = int(r.headers["location"].rsplit("/", 1)[1])
    client.post(f"/matches/{match_id}/toss", data={"winner_id": 1, "decision": "bat"})
    return match_id


def post_ball(
    client: TestClient,
    match_id: int,
    action: str,
    striker: int,
    non_striker: int,
    bowler: int | str,
    **extra: object,
):
    data = {
        "striker": striker,
        "non_striker": non_striker,
        "bowler": bowler,
        "action": action,
        **extra,
    }
    return client.post(f"/matches/{match_id}/balls", data=data, headers=HTMX)

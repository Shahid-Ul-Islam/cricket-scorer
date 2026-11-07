from fastapi.testclient import TestClient

from web_helpers import HTMX, A, H, post_ball, setup_match


def test_json_export_download(client: TestClient) -> None:
    match_id = setup_match(client)
    post_ball(client, match_id, "run:4", H[1], H[2], A[1])
    r = client.get(f"/matches/{match_id}/export.json")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    assert f'filename="match-{match_id}.json"' in r.headers["content-disposition"]
    data = r.json()
    assert data["match"]["id"] == match_id
    assert data["innings"][0]["balls"][0]["runs"] == 4


def test_markdown_export_download(client: TestClient) -> None:
    match_id = setup_match(client)
    post_ball(client, match_id, "run:6", H[1], H[2], A[1])
    r = client.get(f"/matches/{match_id}/scorecard.md")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "attachment" in r.headers["content-disposition"]
    assert r.text.startswith("# Home CC v Away CC")
    assert "| H1 | not out | 6 | 1 | 0 | 1 | 600.00 |" in r.text


def test_export_unknown_match_404(client: TestClient) -> None:
    assert client.get("/matches/99/export.json").status_code == 404
    assert client.get("/matches/99/scorecard.md").status_code == 404


def test_end_to_end_match(client: TestClient) -> None:
    """Two-over match through the web UI, from toss to exports and stats."""
    match_id = setup_match(client, overs=2)

    # First innings: Home 13/1.
    post_ball(client, match_id, "run:1", H[1], H[2], A[1])
    post_ball(client, match_id, "wide:0", H[2], H[1], A[1])
    post_ball(client, match_id, "run:4", H[2], H[1], A[1])
    post_ball(client, match_id, "wicket", H[2], H[1], A[1], dismissal="bowled")
    post_ball(client, match_id, "run:2", H[3], H[1], A[1])
    post_ball(client, match_id, "lb:1", H[3], H[1], A[1])
    post_ball(client, match_id, "run:0", H[1], H[3], A[1])  # end of over 1
    r = post_ball(client, match_id, "run:0", H[1], H[3], A[1])
    assert "consecutive" in r.text  # A1 cannot bowl over 2
    for _ in range(5):
        post_ball(client, match_id, "run:0", H[3], H[1], A[2])
    r = post_ball(client, match_id, "run:4", H[3], H[1], A[2])
    assert "Innings break" in r.text and "need 14 to win" in r.text

    # Second innings: Away chase 14 and fall short (singles rotate the strike).
    for i in range(6):
        striker, non_striker = (A[1], A[2]) if i % 2 == 0 else (A[2], A[1])
        post_ball(client, match_id, "run:1", striker, non_striker, H[5])
    for _ in range(5):
        post_ball(client, match_id, "run:0", A[2], A[1], H[6])
    r = post_ball(client, match_id, "run:6", A[2], A[1], H[6])
    assert "Match finished" in r.text
    assert "Home CC won by 1 run" in r.text

    card = client.get(f"/matches/{match_id}/scorecard").text
    assert "Home CC won by 1 run" in card and "Away CC - 12/0 (2.0 ov)" in card

    stats = client.get(f"/players/{A[1]}").text
    assert "1/8" in stats  # A1: 1 + 1wd + 4 + 2 = 8; the leg-bye is not charged

    md = client.get(f"/matches/{match_id}/scorecard.md").text
    assert "**Home CC won by 1 run**" in md

    # Undo reopens the finished match.
    r = client.post(f"/matches/{match_id}/undo", headers=HTMX)
    assert "Need <b>8</b> off <b>1</b>" in r.text  # 6/0 chasing 14

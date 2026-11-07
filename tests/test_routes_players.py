from fastapi.testclient import TestClient

from web_helpers import A, H, post_ball, setup_match


def play_short_match(client: TestClient) -> int:
    match_id = setup_match(client, overs=1)
    post_ball(client, match_id, "run:6", H[1], H[2], A[1])
    for _ in range(5):
        post_ball(client, match_id, "run:0", H[1], H[2], A[1])
    post_ball(client, match_id, "run:1", A[1], A[2], H[3])  # 1/0 chasing 7
    post_ball(client, match_id, "wicket", A[2], A[1], H[3], dismissal="lbw")
    for _ in range(4):
        post_ball(client, match_id, "run:0", A[3], A[1], H[3])
    return match_id


def test_players_page_lists_career_figures(client: TestClient) -> None:
    play_short_match(client)
    r = client.get("/players")
    assert r.status_code == 200
    # Leaderboard is sorted by runs, H1 (6 runs) first.
    first_row = r.text.split("<tbody>")[1].split("</tr>")[0]
    assert "H1" in first_row and "<td>6</td>" in first_row


def test_player_detail(client: TestClient) -> None:
    play_short_match(client)
    r = client.get(f"/players/{H[3]}")
    assert r.status_code == 200
    assert "Bowling" in r.text and "1/1" in r.text  # best figures
    r = client.get(f"/players/{H[1]}")
    assert "6*" in r.text  # highest score, not out


def test_unknown_player_404(client: TestClient) -> None:
    assert client.get("/players/999").status_code == 404

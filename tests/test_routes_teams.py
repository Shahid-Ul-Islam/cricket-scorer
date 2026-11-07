from fastapi.testclient import TestClient


def test_index_redirects(client: TestClient) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303


def test_create_team_and_add_player(client: TestClient) -> None:
    r = client.post("/teams", data={"name": "Riverside CC"})
    assert r.status_code == 200  # followed the redirect
    assert "Riverside CC" in r.text
    team_url = str(r.url)

    r = client.post(f"{team_url}/players", data={"name": "Amir"})
    assert r.status_code == 200 and "Amir" in r.text

    r = client.get("/teams")
    assert "Riverside CC" in r.text and "1 players" in r.text


def test_add_player_with_htmx_returns_fragment(client: TestClient) -> None:
    client.post("/teams", data={"name": "Riverside"})
    r = client.post("/teams/1/players", data={"name": "Amir"}, headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert r.text.lstrip().startswith('<section id="players">')
    assert "<html" not in r.text


def test_duplicate_team_shows_error(client: TestClient) -> None:
    client.post("/teams", data={"name": "Riverside"})
    r = client.post("/teams", data={"name": "riverside"})
    assert r.status_code == 422
    assert "already exists" in r.text


def test_names_are_escaped(client: TestClient) -> None:
    r = client.post("/teams", data={"name": "<script>x</script>"})
    assert "<script>x</script>" not in r.text
    assert "&lt;script&gt;" in r.text


def test_unknown_team_404(client: TestClient) -> None:
    r = client.get("/teams/999")
    assert r.status_code == 404
    assert "not found" in r.text


def test_static_assets_served(client: TestClient) -> None:
    assert client.get("/static/htmx.min.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200

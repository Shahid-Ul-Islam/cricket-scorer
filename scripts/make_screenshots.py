"""Regenerate the README screenshots from a fictional sample match.

Seeds a temporary SQLite database with a made-up match, runs the app on a free
local port and captures pages with headless Chrome, Chromium or Edge using a
throwaway profile, so the images contain no browser UI and no real names.

    python scripts/make_screenshots.py [--browser PATH] [--out docs/screenshots]
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from cricket_scorer.db import init_db, make_engine, make_session_factory
from cricket_scorer.engine import BallEvent, DismissalType, ExtraType
from cricket_scorer.models import TossDecision
from cricket_scorer.services import matches, teams

ROOT = Path(__file__).resolve().parent.parent

HOME = [
    "Tom Ashby", "Dev Kapoor", "Sam Okafor", "Jamie Reid", "Omar Haddad", "Liam Byrne",
    "Ravi Nair", "Ben Taylor", "Kofi Mensah", "Alex Moreno", "Will Hart",
]  # fmt: skip
AWAY = [
    "Joe Fenwick", "Arjun Rao", "Max Keller", "Noah Price", "Ethan Cole", "Yusuf Ali",
    "Ryan Doyle", "Leo Marsh", "Chris Wong", "Dan Hughes", "Matt Ellis",
]  # fmt: skip

# (file name, path template, window size)
SHOTS = [
    ("live-scoring.png", "/matches/{id}/score", "1280,1000"),
    ("scorecard.png", "/matches/{id}/scorecard", "1280,870"),
]

BROWSER_CANDIDATES = [
    "chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def seed(database_url: str) -> int:
    """Create Riverside CC v Hillcrest Wanderers, 34/2 after 3.3 overs."""
    engine = make_engine(database_url)
    init_db(engine)
    with make_session_factory(engine)() as s:
        home = teams.create_team(s, "Riverside CC")
        away = teams.create_team(s, "Hillcrest Wanderers")
        ids = {}
        for team, names in ((home, HOME), (away, AWAY)):
            for name in names:
                ids[name] = teams.add_player(s, team.id, name).id
        match = matches.create_match(
            s,
            home_team_id=home.id,
            away_team_id=away.id,
            overs_per_side=20,
            venue="Riverside Park",
            date=dt.date(2026, 11, 7),
        )
        matches.record_toss(s, match, home.id, TossDecision.BAT)
        batting_order = iter(HOME)

        def ball(bowler: str, runs: int = 0, extra=None, dismissal=None, fielder=None) -> None:
            innings = matches.current_innings(match)
            assert innings is not None
            state = matches.innings_state(match, innings)
            striker = state.striker or ids[next(batting_order)]
            non_striker = state.non_striker or ids[next(batting_order)]
            event = BallEvent(
                striker,
                non_striker,
                ids[bowler],
                runs=runs,
                extra=extra,
                dismissal=dismissal,
                fielder=ids[fielder] if fielder else None,
            )
            matches.record_ball(s, match, event)

        for r in (1, 0, 4):
            ball("Joe Fenwick", r)
        ball("Joe Fenwick", 0, ExtraType.WIDE)
        for r in (0, 2, 1):
            ball("Joe Fenwick", r)
        ball("Arjun Rao", 0)
        ball("Arjun Rao", 4)
        ball("Arjun Rao", dismissal=DismissalType.BOWLED)
        ball("Arjun Rao", 1)
        ball("Arjun Rao", 1, ExtraType.LEG_BYE)
        ball("Arjun Rao", 6)
        ball("Joe Fenwick", 2)
        ball("Joe Fenwick", 0)
        ball("Joe Fenwick", 0, ExtraType.NO_BALL)
        ball("Joe Fenwick", 4)  # free hit
        ball("Joe Fenwick", 1)
        ball("Joe Fenwick", 0)
        ball("Joe Fenwick", dismissal=DismissalType.CAUGHT, fielder="Ryan Doyle")
        for r in (1, 4, 0):
            ball("Max Keller", r)
        s.commit()
        match_id = match.id
    engine.dispose()
    return match_id


def find_browser(explicit: str | None) -> str:
    for candidate in [explicit, os.environ.get("CHROME_PATH"), *BROWSER_CANDIDATES]:
        if not candidate:
            continue
        found = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if found:
            return found
    sys.exit("No Chrome, Chromium or Edge found; pass --browser or set CHROME_PATH.")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until_up(url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except OSError:
            time.sleep(0.25)
    sys.exit(f"Server did not start at {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--browser", help="path to a Chrome, Chromium or Edge executable")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "screenshots")
    args = parser.parse_args()
    browser = find_browser(args.browser)
    args.out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        database_url = "sqlite:///" + Path(tmp, "demo.db").as_posix()
        match_id = seed(database_url)
        port = free_port()
        server = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "cricket_scorer.web.app:create_app",
                "--factory", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
            ],
            env={**os.environ, "CRICKET_SCORER_DATABASE_URL": database_url},
        )  # fmt: skip
        try:
            base = f"http://127.0.0.1:{port}"
            wait_until_up(f"{base}/matches")
            for name, path, size in SHOTS:
                target = args.out / name
                subprocess.run(
                    [
                        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--no-first-run", "--no-default-browser-check",
                        "--force-device-scale-factor=1",
                        f"--user-data-dir={Path(tmp, 'profile')}",
                        f"--window-size={size}", f"--screenshot={target}",
                        base + path.format(id=match_id),
                    ],
                    check=True,
                    capture_output=True,
                )  # fmt: skip
                print(f"wrote {target}")
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()

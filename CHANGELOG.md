# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project scaffold: `pyproject.toml`, ruff config, MIT license, package skeleton.
- GitHub Actions CI running ruff (lint + format) and pytest on Python 3.12.
- Engine domain types: `BallEvent`, `ExtraType`, `DismissalType` (incl. retired hurt/out),
  `InningsConfig`.
- Innings replay engine: run accounting, strike rotation on odd runs and at end of over,
  maidens, bowler rules (no consecutive overs, optional per-bowler cap), run rate,
  required rate, partnership, this-over summary, innings end on overs or target.
- Extras handling (wide/no-ball penalty, runs off no-balls to the batter, byes and
  leg-byes not charged to the bowler) and free hit after a no-ball, carried over wides.
- Dismissals: bowled, caught, lbw, run out (either batter, with runs completed), stumped,
  hit wicket, retired hurt (may resume) and retired out; rules for which dismissals are
  possible off each extra and on a free hit; fall of wickets; all-out ends the innings.
- Undo of the last event by replaying the rest of the innings.
- SQLAlchemy models (Team, Player, Match, Innings, Over, Ball) and SQLite session helpers;
  database URL configurable via `CRICKET_SCORER_DATABASE_URL`.
- Services for teams/players and the match lifecycle: create match, toss, record ball
  (team checks + engine validation), automatic second innings, result (by runs, by
  wickets, tie), close innings early, and undo across innings and completed matches.
- Web app factory with Jinja2 layout, vendored htmx 2.0.4, light/dark stylesheet, team
  and player pages (HTMX add-player), 404 page, and `cricket-scorer` / `python -m
  cricket_scorer` entry point.
- Match list (scores, live/result status), new-match form (overs, players per side,
  optional bowler cap, date, venue) and toss page.
- Live HTMX scoring page: pick striker/non-striker/bowler, buttons for 0/1/2/3/4/6,
  wides, no-balls, byes, leg-byes, wicket/retirement form, undo and end-innings; shows
  score, run rate, target, required rate, partnership, free hit and this-over summary.
- Scorecard page per match: batting card with dismissal text, extras breakdown, totals,
  fall of wickets and bowling card (O, M, R, W, economy, wides, no-balls).
- Player stats from completed matches: career batting (innings, not outs, runs, highest,
  average, strike rate, 50s/100s) and bowling (overs, wickets, best figures, average,
  economy), with a players leaderboard and innings-by-innings detail.
- Exports: full match as JSON (`/matches/{id}/export.json`, schema version 1, every ball)
  and scorecard as Markdown (`/matches/{id}/scorecard.md`), linked from the scorecard.

### Removed
- Local `.claude/settings.local.json` from version control.

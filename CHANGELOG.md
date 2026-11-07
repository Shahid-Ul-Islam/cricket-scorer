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

### Removed
- Local `.claude/settings.local.json` from version control.

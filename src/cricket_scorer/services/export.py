"""Exports: a full match as JSON and a scorecard as Markdown."""

from __future__ import annotations

from typing import Any

from cricket_scorer import __version__
from cricket_scorer.models import Match, Team
from cricket_scorer.services.matches import match_innings
from cricket_scorer.services.scorecard import Scorecard

JSON_SCHEMA_VERSION = 1


def _team(team: Team) -> dict[str, Any]:
    return {
        "id": team.id,
        "name": team.name,
        "players": [{"id": p.id, "name": p.name} for p in team.players],
    }


def match_to_dict(match: Match) -> dict[str, Any]:
    """Everything needed to rebuild the match: metadata plus every ball."""
    innings = []
    for view in match_innings(match):
        s = view.state
        innings.append(
            {
                "number": view.innings.number,
                "batting_team_id": view.innings.batting_team_id,
                "bowling_team_id": view.innings.bowling_team_id,
                "closed": view.innings.closed,
                "target": s.config.target,
                "summary": {
                    "runs": s.runs,
                    "wickets": s.wickets,
                    "overs": s.overs,
                    "extras": {k.value: v for k, v in s.extras.items()},
                },
                "balls": [
                    {
                        "seq": seq,
                        "over": a.over_index + 1,
                        "label": a.label,
                        "striker_id": a.event.striker,
                        "non_striker_id": a.event.non_striker,
                        "bowler_id": a.event.bowler,
                        "runs": a.event.runs,
                        "extra": a.event.extra.value if a.event.extra else None,
                        "dismissal": a.event.dismissal.value if a.event.dismissal else None,
                        "dismissed_id": a.event.out_player,
                        "fielder_id": a.event.fielder,
                        "free_hit": a.free_hit,
                    }
                    for seq, a in enumerate(s.applied)
                ],
            }
        )
    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "generator": f"cricket-scorer {__version__}",
        "match": {
            "id": match.id,
            "date": match.date.isoformat(),
            "venue": match.venue,
            "overs_per_side": match.overs_per_side,
            "players_per_side": match.players_per_side,
            "max_overs_per_bowler": match.max_overs_per_bowler,
            "home_team": _team(match.home_team),
            "away_team": _team(match.away_team),
            "toss_winner_id": match.toss_winner_id,
            "toss_decision": match.toss_decision.value if match.toss_decision else None,
            "status": match.status.value,
            "winner_id": match.winner_id,
            "result": match.result,
        },
        "innings": innings,
    }


def _cell(value: object) -> str:
    text = "-" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _rate(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _row(*cells: object) -> str:
    return "| " + " | ".join(_cell(c) for c in cells) + " |"


def scorecard_markdown(card: Scorecard) -> str:
    lines = [f"# {card.title}", ""]
    meta = [card.date]
    if card.venue:
        meta.append(card.venue)
    meta.append(f"{card.overs_per_side} overs per side")
    lines.append(" · ".join(meta) + "  ")
    if card.toss:
        lines.append(card.toss + "  ")
    if card.result:
        lines.append(f"**{card.result}**")
    elif card.innings:
        lines.append("_In progress_")
    lines.append("")

    for inn in card.innings:
        heading = f"## {inn.batting_team} - {inn.total} ({inn.overs} ov)"
        if inn.target:
            heading += f", target {inn.target}"
        lines += [heading, ""]
        lines += [
            "| Batter | Dismissal | R | B | 4s | 6s | SR |",
            "|---|---|--:|--:|--:|--:|--:|",
        ]
        for b in inn.batting:
            lines.append(
                _row(b.name, b.how_out, b.runs, b.balls, b.fours, b.sixes, _rate(b.strike_rate))
            )
        lines.append(_row("Extras", inn.extras_detail or "-", inn.total_extras, "", "", "", ""))
        lines.append(
            _row(
                "**Total**",
                f"{inn.wickets} wkts, {inn.overs} ov, RR {_rate(inn.run_rate)}",
                f"**{inn.runs}**",
                "",
                "",
                "",
                "",
            )
        )
        lines.append("")
        if inn.fall_of_wickets:
            fow = ", ".join(
                f"{f.number}-{f.runs} ({f.name}, {f.overs} ov)" for f in inn.fall_of_wickets
            )
            lines += [f"**Fall of wickets:** {fow}", ""]
        if inn.bowling:
            lines += [
                f"| Bowler ({_cell(inn.bowling_team)}) | O | M | R | W | Econ | Wd | NB |",
                "|---|--:|--:|--:|--:|--:|--:|--:|",
            ]
            for bw in inn.bowling:
                lines.append(
                    _row(
                        bw.name,
                        bw.overs,
                        bw.maidens,
                        bw.runs,
                        bw.wickets,
                        _rate(bw.economy),
                        bw.wides,
                        bw.no_balls,
                    )
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"

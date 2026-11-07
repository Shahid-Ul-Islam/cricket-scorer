"""Scorecards: batting and bowling cards, extras and fall of wickets."""

from __future__ import annotations

from dataclasses import dataclass

from cricket_scorer.engine import DismissalType, ExtraType
from cricket_scorer.engine.innings import BatterStats
from cricket_scorer.models import Match, MatchStatus
from cricket_scorer.services.matches import match_innings


@dataclass(frozen=True)
class BattingRow:
    player_id: int
    name: str
    how_out: str
    runs: int
    balls: int
    fours: int
    sixes: int
    strike_rate: float | None


@dataclass(frozen=True)
class BowlingRow:
    player_id: int
    name: str
    overs: str
    maidens: int
    runs: int
    wickets: int
    economy: float | None
    wides: int
    no_balls: int


@dataclass(frozen=True)
class FallOfWicketRow:
    number: int
    runs: int
    overs: str
    name: str


@dataclass(frozen=True)
class InningsCard:
    number: int
    batting_team: str
    bowling_team: str
    runs: int
    wickets: int
    overs: str
    run_rate: float | None
    target: int | None
    extras: dict[ExtraType, int]
    total_extras: int
    batting: list[BattingRow]
    bowling: list[BowlingRow]
    fall_of_wickets: list[FallOfWicketRow]

    @property
    def total(self) -> str:
        return f"{self.runs}/{self.wickets}"

    @property
    def extras_detail(self) -> str:
        parts = [
            ("b", self.extras[ExtraType.BYE]),
            ("lb", self.extras[ExtraType.LEG_BYE]),
            ("w", self.extras[ExtraType.WIDE]),
            ("nb", self.extras[ExtraType.NO_BALL]),
        ]
        return ", ".join(f"{k} {v}" for k, v in parts if v)


@dataclass(frozen=True)
class Scorecard:
    match_id: int
    title: str
    date: str
    venue: str | None
    overs_per_side: int
    toss: str | None
    status: MatchStatus
    result: str | None
    innings: list[InningsCard]


def how_out(b: BatterStats, names: dict[int, str]) -> str:
    def n(pid: int | None) -> str:
        return names.get(pid, "?") if pid is not None else ""

    bowler, fielder = n(b.bowler), n(b.fielder)
    match b.dismissal:
        case None:
            return "not out"
        case DismissalType.BOWLED:
            return f"b {bowler}"
        case DismissalType.CAUGHT:
            if b.fielder is not None and b.fielder == b.bowler:
                return f"c & b {bowler}"
            return f"c {fielder} b {bowler}" if fielder else f"caught b {bowler}"
        case DismissalType.LBW:
            return f"lbw b {bowler}"
        case DismissalType.STUMPED:
            return f"st {fielder} b {bowler}" if fielder else f"stumped b {bowler}"
        case DismissalType.HIT_WICKET:
            return f"hit wicket b {bowler}"
        case DismissalType.RUN_OUT:
            return f"run out ({fielder})" if fielder else "run out"
        case DismissalType.RETIRED_HURT:
            return "retired hurt"
        case DismissalType.RETIRED_OUT:
            return "retired out"


def build_scorecard(match: Match) -> Scorecard:
    names = {p.id: p.name for t in (match.home_team, match.away_team) for p in t.players}
    cards: list[InningsCard] = []
    for view in match_innings(match):
        s = view.state
        batting = [
            BattingRow(
                player_id=b.player,
                name=names[b.player],
                how_out=how_out(b, names),
                runs=b.runs,
                balls=b.balls,
                fours=b.fours,
                sixes=b.sixes,
                strike_rate=b.strike_rate,
            )
            for b in s.batters.values()
        ]
        bowling = [
            BowlingRow(
                player_id=bw.player,
                name=names[bw.player],
                overs=bw.overs,
                maidens=bw.maidens,
                runs=bw.runs,
                wickets=bw.wickets,
                economy=bw.economy,
                wides=bw.wides,
                no_balls=bw.no_balls,
            )
            for bw in s.bowlers.values()
        ]
        fow = [
            FallOfWicketRow(f.number, f.runs, f.overs, names[f.player]) for f in s.fall_of_wickets
        ]
        cards.append(
            InningsCard(
                number=view.innings.number,
                batting_team=view.innings.batting_team.name,
                bowling_team=view.innings.bowling_team.name,
                runs=s.runs,
                wickets=s.wickets,
                overs=s.overs,
                run_rate=s.run_rate,
                target=s.config.target,
                extras=dict(s.extras),
                total_extras=s.total_extras,
                batting=batting,
                bowling=bowling,
                fall_of_wickets=fow,
            )
        )

    toss = None
    if match.toss_winner is not None and match.toss_decision is not None:
        toss = f"{match.toss_winner.name} won the toss and elected to {match.toss_decision.value}"
    return Scorecard(
        match_id=match.id,
        title=match.title,
        date=match.date.isoformat(),
        venue=match.venue,
        overs_per_side=match.overs_per_side,
        toss=toss,
        status=match.status,
        result=match.result,
        innings=cards,
    )

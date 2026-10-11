"""Each team's chance of winning a game, from a rating built on results.

A rating says how much better a team is than an average FBS team, in units a
little smaller than a point. Before each game the two ratings (and home field)
give an expected margin; afterwards both teams move toward what actually
happened, quickly early in the season and slowly later, and a blowout counts
for a little less than its full margin. A team starts a season on most of where
it finished the last one, measured from the average of its own division, so a
school from the division below does not drift up toward FBS over the summer.

Tested on 4,547 games from 2021 to 2025, always predicting a game from what was
known before it: the favorite won 74.3% of them (the home team wins 63.0%),
and teams given 70-80% won 73%. The settings in config.py were chosen on those
same games, so expect slightly worse on new ones.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import config

SEED_FILE = Path(__file__).resolve().parents[1] / "ratings" / "seed.json"


def seed() -> dict:
    """{"season": the season these ratings finished, "ratings": {team: rating}}:
    where teams stood before this site kept its own ratings."""
    return json.loads(SEED_FILE.read_text()) if SEED_FILE.exists() else {}


def chance(home: float, away: float, neutral: bool = False) -> float:
    """The home team's chance of winning."""
    gap = home - away + (0.0 if neutral else config.ODDS_HOME)
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, gap / config.ODDS_SCALE))))


def _soft(x: float) -> float:
    return config.ODDS_SOFT_CAP * math.tanh(x / config.ODDS_SOFT_CAP)


def rate(games: list[dict], before: dict, fbs: set) -> tuple[dict, dict]:
    """Walk through a season's games in order. `before` is last season's final
    ratings and `fbs` the ids of this season's FBS teams. Returns (ratings now,
    {game id: the home team's chance as it stood before that game was played})."""
    top = [v for t, v in before.items() if t in fbs]
    rest = [v for t, v in before.items() if t not in fbs]
    mean_top = sum(top) / len(top) if top else 0.0
    mean_rest = sum(rest) / len(rest) if rest else config.ODDS_NEW
    rating, played, pregame = {}, {}, {}

    def start(team):
        if team in before:
            mean = mean_top if team in fbs else mean_rest
            return mean + config.ODDS_KEEP * (before[team] - mean)
        return config.ODDS_NEW / 3 if team in fbs else config.ODDS_NEW

    for g in sorted(games, key=lambda g: (g["date"], g["start"] or 0, g["id"])):
        h, a = g["home"]["id"], g["away"]["id"]
        for t in (h, a):
            if t not in rating:
                rating[t] = start(t)
        hs, vs = g["home"].get("score"), g["away"].get("score")
        if g["state"] != "final" or hs is None or vs is None or hs == vs:
            continue
        neutral = bool(g.get("neutral"))
        pregame[g["id"]] = chance(rating[h], rating[a], neutral)
        expected = rating[h] - rating[a] + (0.0 if neutral else config.ODDS_HOME)
        surprise = _soft(hs - vs) - _soft(expected)
        for t, sign in ((h, 1.0), (a, -1.0)):
            step = config.ODDS_STEP / (1.0 + played.get(t, 0) / config.ODDS_SETTLE) + config.ODDS_MIN_STEP
            rating[t] += sign * step * surprise
            played[t] = played.get(t, 0) + 1
    return rating, pregame

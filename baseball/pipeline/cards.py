"""What a player's card shows beyond his ratings: every game he has played,
his season highs and his career.

These are written one file per team (cards/<team>.json), so a card loads only
its own team's lines.
"""
from __future__ import annotations

from .players import LOG, innings

# positions in a game line (see players.compute): the stats start after the result
M, DATE, OPP, OPP_NAME, HOME, RESULT = range(6)
AT = {k: 6 + i for i, k in enumerate(LOG)}
HIGHS_BAT = [("Hits", "h"), ("Home runs", "hr"), ("Runs batted in", "rbi"), ("Runs", "r"), ("Walks", "bb")]
HIGHS_PIT = [("Strikeouts", "pk"), ("Innings", "outs"), ("Pitches", "pc")]


def one(lines: list[list], player: dict, career: list, ranked: set) -> dict:
    """One player's part of his team's file. `lines` are his games, oldest
    first; `career` his seasons as ESPN lists them (empty until they are read)."""
    pitcher = player.get("group") in ("SP", "RP")
    highs = []
    for label, key in (HIGHS_PIT if pitcher else HIGHS_BAT):
        best = max(lines, key=lambda r: (r[AT[key]], r[DATE]), default=None)
        if best is not None and best[AT[key]] > 0:
            shown = float(innings(best[AT[key]])) if key == "outs" else best[AT[key]]       # 20 outs reads 6.2
            highs.append([label, shown, best[OPP], best[OPP_NAME], best[DATE], best[M]])
    if pitcher:
        starts = [r for r in lines if r[AT["outs"]] >= 18 and r[AT["er"]] <= 3]
        marks = [[label, n] for label, n in (("quality starts", len(starts)),
                                             ("ten-strikeout games", sum(1 for r in lines if r[AT["pk"]] >= 10)),
                                             ("scoreless outings", sum(1 for r in lines if r[AT["outs"]] and not r[AT["pr"]]))) if n]
    else:
        marks = [[label, n] for label, n in (("multi-hit games", sum(1 for r in lines if r[AT["h"]] >= 2)),
                                             ("home run games", sum(1 for r in lines if r[AT["hr"]] >= 1)),
                                             ("two-homer games", sum(1 for r in lines if r[AT["hr"]] >= 2))) if n]
    return {"games": lines[::-1], "highs": highs, "marks": marks, "career": career or []}


def build(rated: dict, logs: dict, careers: dict, ranked: set) -> dict:
    """{team: {player id: his card's extra lines}} for everyone in `rated`.
    `careers` is {player id: his seasons}."""
    out = {}
    for p in rated["players"]:
        out.setdefault(p["team_id"], {})[p["id"]] = one(logs.get(p["id"]) or [], p, careers.get(p["id"]) or [], ranked)
    return out

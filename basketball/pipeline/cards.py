"""What a player's card shows beyond his ratings: every game he has played,
his season highs, how he has done against ranked teams, and his career.

These are written one file per team (cards/<team>.json), so a card loads only
its own team's lines.
"""
from __future__ import annotations

from . import config
from .players import LOG

# positions in a game line (see players.compute): the stats start after the result
M, DATE, OPP, OPP_NAME, HOME, RESULT = range(6)
AT = {k: 6 + i for i, k in enumerate(LOG)}
HIGHS = [("Points", "pts"), ("Rebounds", "reb"), ("Assists", "ast"), ("Steals", "stl"), ("Blocks", "blk"), ("Three-pointers", "tpm")]
DOUBLE = ["pts", "reb", "ast", "stl", "blk"]         # ten or more in two of these is a double-double


def one(lines: list[list], player: dict, career: list, ranked: set) -> dict:
    """One player's part of his team's file. `lines` are his games, oldest
    first; `career` his seasons as ESPN lists them (empty until they are read)."""
    highs = []
    for label, key in HIGHS:
        best = max(lines, key=lambda r: (r[AT[key]], r[DATE]), default=None)
        if best is not None and best[AT[key]] > 0:
            highs.append([label, best[AT[key]], best[OPP], best[OPP_NAME], best[DATE], best[M]])
    tens = [sum(1 for k in DOUBLE if r[AT[k]] >= 10) for r in lines]
    marks = [[label, n] for label, n in ((f"{config.BIG_GAME}-point games", sum(1 for r in lines if r[AT["pts"]] >= config.BIG_GAME)),
                                         ("double-doubles", sum(1 for n in tens if n == 2)),
                                         ("triple-doubles", sum(1 for n in tens if n >= 3))) if n]
    out = {"games": lines[::-1], "highs": highs, "marks": marks, "career": career or []}
    against = [r for r in lines if r[OPP] in ranked]
    if against:
        out["ranked"] = {"gp": len(against), "w": sum(1 for r in against if r[RESULT].startswith("W")),
                         "tot": [sum(r[6 + i] for r in against) for i in range(len(LOG))]}
    return out


def build(rated: dict, logs: dict, careers: dict, ranked: set) -> dict:
    """{team: {player id: his card's extra lines}} for everyone in `rated`.
    `careers` is {player id: his seasons}."""
    out = {}
    for p in rated["players"]:
        out.setdefault(p["team_id"], {})[p["id"]] = one(logs.get(p["id"]) or [], p, careers.get(p["id"]) or [], ranked)
    return out

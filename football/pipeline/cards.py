"""What a player's card shows beyond his ratings: every game he has played,
his season highs, how he has done against ranked teams, and his career.

These are written one file per team (cards/<team>.json), so a card loads only
its own team's lines.
"""
from __future__ import annotations

from .players import LOG

# positions in a game line (see players.compute): the stats start after the result
M, DATE, OPP, OPP_NAME, HOME, RESULT = range(6)
AT = {k: 6 + i for i, k in enumerate(LOG)}
# season highs worth showing, by position: (label, the numbers added together)
HIGHS = {
    "QB": [("Passing yards", ["pyds"]), ("Passing touchdowns", ["ptd"]), ("Completions", ["cmp"]), ("Rushing yards", ["ryds"])],
    "RB": [("Rushing yards", ["ryds"]), ("Carries", ["car"]), ("Rushing touchdowns", ["rtd"]), ("Receiving yards", ["recyds"])],
    "WR": [("Receiving yards", ["recyds"]), ("Catches", ["rec"]), ("Receiving touchdowns", ["rectd"])],
    "TE": [("Receiving yards", ["recyds"]), ("Catches", ["rec"]), ("Receiving touchdowns", ["rectd"])],
    "DL": [("Tackles", ["tkl"]), ("Tackles for loss", ["tfl"]), ("Sacks", ["sk"])],
    "LB": [("Tackles", ["tkl"]), ("Tackles for loss", ["tfl"]), ("Sacks", ["sk"]), ("Passes defended", ["pd"])],
    "DB": [("Tackles", ["tkl"]), ("Passes defended", ["pd"]), ("Interceptions", ["dint"])],
    "K": [("Field goals", ["fgm"]), ("Extra points", ["xpm"])],
    "P": [("Punts", ["punts"]), ("Punt yards", ["puntyds"])],
}
# games worth counting: (what it is called, the number, at least this many)
MARKS = [("300-yard passing games", "pyds", 300), ("100-yard rushing games", "ryds", 100), ("100-yard receiving games", "recyds", 100),
         ("games with 10 or more tackles", "tkl", 10)]


def one(lines: list[list], player: dict, career: list, ranked: set) -> dict:
    """One player's part of his team's file. `lines` are his games, oldest
    first; `career` his seasons as ESPN lists them (empty until they are read)."""
    highs = []
    for label, keys in HIGHS.get(player["pos"], []):
        def get(r, keys=keys):
            return sum(r[AT[k]] for k in keys)
        best = max(lines, key=lambda r: (get(r), r[DATE]), default=None)
        if best is not None and get(best) > 0:
            highs.append([label, get(best), best[OPP], best[OPP_NAME], best[DATE], best[M]])
    marks = [[label, n] for label, key, least in MARKS for n in [sum(1 for r in lines if r[AT[key]] >= least)] if n]
    out = {"games": lines[::-1], "highs": highs, "marks": marks, "career": career or []}
    against = [r for r in lines if r[OPP] in ranked]
    if against:
        out["ranked"] = {"gp": len(against), "w": sum(1 for r in against if r[RESULT].startswith("W")),
                         "tot": [round(sum(r[6 + i] for r in against), 1) for i in range(len(LOG))]}
    return out


def build(rated: dict, logs: dict, careers: dict, ranked: set) -> dict:
    """{team: {player id: his card's extra lines}} for everyone in `rated`.
    `careers` is {player id: his seasons}."""
    out = {}
    for p in rated["players"]:
        out.setdefault(p["team_id"], {})[p["id"]] = one(logs.get(p["id"]) or [], p, careers.get(p["id"]) or [], ranked)
    return out

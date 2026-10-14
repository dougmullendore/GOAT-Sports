"""Rate players against each other, from the box scores.

Everything here compares a player with the other regulars at his position on
the teams given (this week's top 25, all of Division I, or the NBA).

Impact starts from game score, the box score rolled into one number that reads
like points:
    points + 0.4 x field goals made - 0.7 x field goals tried
    - 0.4 x free throws missed + 0.7 x offensive rebounds + 0.3 x defensive rebounds
    + steals + 0.7 x assists + 0.7 x blocks - 0.4 x fouls - turnovers
Impact is a player's game score beyond what an average regular at his position
puts up in the same minutes. It is shown in four parts:
  scoring     points, less the cost of the shots and free throws he missed
  rebounding  offensive rebounds at 0.7, defensive at 0.3
  playmaking  assists at 0.7, less turnovers
  defense     steals, blocks at 0.7, less fouls at 0.4
It is a box-score measure. It cannot see defense that leaves no number, who was
on the floor, or the strength of the opponent.
"""
from __future__ import annotations

from . import config
from .espn import COLS

POSITIONS = ["G", "F", "C"]
PARTS = ["score", "board", "play", "def"]
REGULAR_GAMES = 0.4          # a regular has played in at least this share of his team's games
MIN_POOL = 8                 # no percentile unless at least this many players qualify

STATS = [c for c in COLS if c != "pm"]
# a game line for a player's card: [game, date, opponent id, opponent, at home, result] and then these
LOG = ["min", "pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "ast", "stl", "blk", "to", "pf", "pm"]

# (key, higher is better, who is ranked on it)
METRICS = [
    ("impact_g", True, "all"), ("score", True, "all"), ("board", True, "all"), ("play", True, "all"), ("def", True, "all"),
    ("pts_g", True, "all"), ("fg_pct", True, "shoots"), ("tp_pct", True, "threes"), ("ft_pct", True, "fts"), ("efg", True, "shoots"),
    ("ts", True, "shoots"), ("reb_g", True, "all"), ("ast_g", True, "all"), ("stl_g", True, "all"), ("blk_g", True, "all"),
    ("to_g", False, "all"), ("ast_to", True, "passes"), ("min_g", True, "all"),
]


def _r(v, nd=2):
    return None if v is None else round(v, nd)


def position(abbr: str) -> str | None:
    """Guard, forward or center, from whatever the roster or the box score calls him ("PG", "G-F", "PF")."""
    a = (abbr or "").upper()
    if not a:
        return None
    first = a.replace("-", "/").split("/")[0]
    if first in ("C",) or first.startswith("C"):
        return "C"
    if "F" in first:
        return "F"
    if "G" in first:
        return "G"
    return None


def parts(p: dict) -> dict:
    """A stat line's game score, in its four parts."""
    return {"score": p["pts"] + 0.4 * p["fgm"] - 0.7 * p["fga"] - 0.4 * (p["fta"] - p["ftm"]),
            "board": 0.7 * p["oreb"] + 0.3 * p["dreb"],
            "play": 0.7 * p["ast"] - p["to"],
            "def": p["stl"] + 0.7 * p["blk"] - 0.4 * p["pf"]}


def compute(ranked: list[dict], games: list[dict], boxes: dict, rosters: dict, logs: dict | None = None, kinds: tuple | None = None) -> dict:
    """Every player who has got on the court for the given teams (the ranked 25, all of
    Division I, or the NBA), with totals, rates, impact and percentiles, each measured against
    the players of those teams. `rosters` is {team: {"players": {id: [name, number, position, ...]}}}.
    Only regular-season and tournament games count; the NBA's playoffs are listed but left
    out of the season's numbers. If `logs` is given it is filled with each player's
    game-by-game lines, oldest first:
    {player id: [[game, date, opponent id, opponent, at home, result, ...LOG], ...]}."""
    rank = {t["id"]: t for t in ranked if t["id"]}
    players, team_games = {}, {t: 0 for t in rank}
    at = {c: 5 + i for i, c in enumerate(COLS)}
    counted = kinds or ((2, 3) if config.POLL_TYPE else (2,))          # college: the tournaments are part of the season;
    # `kinds` (1,) counts the NBA's warm-up games instead, while they are all there is
    for g in sorted(games, key=lambda g: (g["date"], g["start"] or 0, g["id"])):
        box = boxes.get(str(g["id"]))
        if g["state"] != "final" or not box or g.get("kind", 2) not in counted:
            continue
        for side, other in (("home", "away"), ("away", "home")):
            team = g[side]["id"]
            rows = (box.get("players") or {}).get(side) or []
            if team not in rank or not rows:
                continue
            team_games[team] += 1
            mine, theirs = g[side].get("score"), g[other].get("score")
            result = "" if mine is None or theirs is None else f"{'W' if mine > theirs else 'L'} {mine}-{theirs}"
            for r in rows:
                if r[at["min"]] <= 0 and not any(r[at[c]] for c in STATS if c != "min"):
                    continue
                p = players.setdefault(r[0], {"id": r[0], "team_id": team, "name": r[1], "num": r[2], "box_pos": {}, "gp": 0, "gs": 0, "pm": 0,
                                              **{s: 0 for s in STATS}})
                p["team_id"] = team                # traded in mid-season: his numbers go with him to his newest team
                p["gp"] += 1
                p["gs"] += r[4]
                if r[3]:
                    p["box_pos"][r[3]] = p["box_pos"].get(r[3], 0) + 1
                for s in STATS:
                    p[s] += r[at[s]]
                p["pm"] += r[at["pm"]]
                if logs is not None:
                    logs.setdefault(r[0], []).append([g["id"], g["date"], g[other]["id"], g[other].get("name") or g[other]["id"],
                                                     int(side == "home"), result] + [r[at[s]] for s in LOG])

    # who he is: the roster's word first, the box score's otherwise
    for p in players.values():
        listed = ((rosters.get(p["team_id"]) or {}).get("players") or {}).get(p["id"])
        p["pos"] = position(listed[2]) if listed else None
        if listed:
            p["name"], p["num"], p["listed"] = listed[0] or p["name"], listed[1] or p["num"], listed
        if not p["pos"] and p["box_pos"]:
            p["pos"] = position(max(p["box_pos"], key=p["box_pos"].get))
        p["pos"] = p["pos"] or "G"
    everyone = list(players.values())
    for p in everyone:
        tg = team_games[p["team_id"]]
        p["regular"] = tg > 0 and p["gp"] >= REGULAR_GAMES * tg and p["min"] >= config.REGULAR_MINUTES * p["gp"]
        p["parts"] = parts(p)

    # What an average regular at each position puts up per minute, part by part.
    regulars = [p for p in everyone if p["regular"]] or everyone
    base = {}
    for pos in POSITIONS:
        grp = [p for p in regulars if p["pos"] == pos] or regulars
        minutes = sum(p["min"] for p in grp)
        base[pos] = {k: (sum(p["parts"][k] for p in grp) / minutes if minutes else 0.0) for k in PARTS}

    out = []
    for p in everyone:
        b, n, m = base[p["pos"]], p["gp"], p["min"]
        part = {k: p["parts"][k] - m * b[k] for k in PARTS}
        impact = sum(part.values())
        shots = p["fga"] + 0.44 * p["fta"]
        v = {"impact_g": impact / n, **{k: part[k] / n for k in PARTS},
             "pts_g": p["pts"] / n, "fg_pct": 100 * p["fgm"] / p["fga"] if p["fga"] else None,
             "tp_pct": 100 * p["tpm"] / p["tpa"] if p["tpa"] else None, "ft_pct": 100 * p["ftm"] / p["fta"] if p["fta"] else None,
             "efg": 100 * (p["fgm"] + 0.5 * p["tpm"]) / p["fga"] if p["fga"] else None,
             "ts": 100 * p["pts"] / (2 * shots) if shots else None,
             "reb_g": p["reb"] / n, "ast_g": p["ast"] / n, "stl_g": p["stl"] / n, "blk_g": p["blk"] / n, "to_g": p["to"] / n,
             "ast_to": p["ast"] / p["to"] if p["to"] else None, "min_g": m / n}
        can = {"all": True, "shoots": p["fga"] / n >= 3, "threes": p["tpa"] / n >= 1, "fts": p["fta"] / n >= 1, "passes": p["ast"] / n >= 1}
        t = rank[p["team_id"]]
        tot = {s: p[s] for s in STATS if p[s]}
        if p["gs"]:
            tot["gs"] = p["gs"]
        if p["pm"]:
            tot["pm"] = p["pm"]
        row = {"id": p["id"], "name": p["name"], "team": t["name"], "team_id": p["team_id"], "team_rank": t["rank"],
               "num": p["num"] if p["num"] != "" else None, "pos": p["pos"], "gp": n, "regular": p["regular"], "impact": impact,
               "_v": v, "_can": can, "tot": tot}
        listed = p.get("listed")
        if listed:
            bio = {}
            if listed[3]:
                bio["ht"] = f"{listed[3] // 12}-{listed[3] % 12}"
            if listed[4]:
                bio["wt"] = listed[4]
            if listed[5]:
                bio["yr"] = listed[5]
            if listed[6]:
                bio["home"] = listed[6]
            if len(listed) > 8 and listed[8]:
                bio["col"] = listed[8]
            if bio:
                row["bio"] = bio
            if listed[7] and config.SHOW_PHOTOS:
                row["ph"] = 1                   # he has a photo: the page builds its address from his id
        out.append(row)

    # Percentiles: against regulars at the same position who do that job.
    keys = [m[0] for m in METRICS]
    for pos in POSITIONS:
        for key, higher, who in METRICS:
            pool = [q for q in out if q["pos"] == pos and q["regular"] and q["_can"][who] and q["_v"][key] is not None]
            if len(pool) < MIN_POOL:
                continue
            vals = sorted(q["_v"][key] for q in pool)
            for q in pool:
                x = q["_v"][key]
                below = sum(1 for y in vals if y < x) + 0.5 * sum(1 for y in vals if y == x)
                pct = 100 * below / len(vals)
                q.setdefault("_pct", {})[key] = int(min(99, max(1, round(pct if higher else 100 - pct))))

    # Ranks: by impact per game among regulars, overall and at the position.
    ordered = sorted((q for q in out if q["regular"]), key=lambda q: (-q["_v"]["impact_g"], -q["impact"]))
    seen = {}
    for i, q in enumerate(ordered):
        q["rank"] = i + 1
        seen[q["pos"]] = seen.get(q["pos"], 0) + 1
        q["pos_rank"] = seen[q["pos"]]
    rows = []
    for q in sorted(out, key=lambda q: (q.get("rank") or 10**6, -q["_v"]["impact_g"])):
        row = {k: q[k] for k in ("id", "name", "team", "team_id", "team_rank", "num", "pos", "gp", "regular", "tot")}
        row.update(rank=q.get("rank"), pos_rank=q.get("pos_rank"), impact=_r(q["impact"], 1), v=[_r(q["_v"][k], 2) for k in keys])
        if q.get("_pct"):
            row["pct"] = [q["_pct"].get(k) for k in keys]       # percentiles, for regulars only
        for extra in ("bio", "ph"):
            if extra in q:
                row[extra] = q[extra]
        rows.append(row)
    return {"metrics": keys, "players": rows, "regulars": len(ordered), "pos_regulars": seen,
            "teams": [{"id": t, "name": rank[t]["name"], "rank": rank[t]["rank"], "games": team_games[t]}
                      for t in sorted(rank, key=lambda t: (rank[t]["rank"] is None, rank[t]["rank"] or 0, rank[t]["name"]))],
            "baseline": {k: {a: _r(b, 4) for a, b in base[k].items()} for k in POSITIONS},
            "weights": {"regular_games": REGULAR_GAMES, "regular_minutes": config.REGULAR_MINUTES}}

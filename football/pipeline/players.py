"""Rate players against each other, from the box scores.

Everything here compares a player with the other regulars at his position on
the teams given (this week's top 25, or all of FBS).

Impact is points added: how many more points a player produced than an average
regular at his position would have, given the same chances. A yard is worth
0.07 of a point (about 14 yards to a point); a touchdown counts as 20 more
yards and a turnover as 45 lost, the weights of adjusted yards per attempt.
  passing    yards, touchdowns and interceptions against the position's average
             on his attempts; the passer keeps 60% and his receivers get the rest
  rushing    yards and touchdowns against the position's average on his carries
  receiving  40% of his receiving yards and touchdowns beyond what the
             position's average regular gets from the same number of team passes
  defense    tackles, tackles for loss, sacks, hurries, passes defended,
             interceptions, fumbles recovered and touchdowns, each given a value
             in points, beyond the position's average per game
  kicking    field goals and extra points against the average on the same
             kicks; punt yardage against the average punt; return yardage
             against the average return
  fumbles    each fumble lost, as a turnover
It is a box-score measure. It cannot see blocking, coverage, who was on the
field, or the strength of the opponent, and it has nothing to say about
offensive linemen, who have no numbers in a box score.
"""
from __future__ import annotations

from . import config
from .espn import CATS

# roster positions, as ESPN writes them, to the nine groups players are compared in
POS_GROUPS = {"QB": "QB", "RB": "RB", "FB": "RB", "HB": "RB", "TB": "RB", "WR": "WR", "TE": "TE",
              "DE": "DL", "DT": "DL", "NT": "DL", "DL": "DL", "EDGE": "DL", "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB",
              "CB": "DB", "S": "DB", "DB": "DB", "FS": "DB", "SS": "DB", "NB": "DB", "PK": "K", "K": "K", "P": "P"}
POSITIONS = ["QB", "RB", "WR", "TE", "DL", "LB", "DB", "K", "P"]
PARTS = ["pass", "rush", "recv", "def", "st", "fum"]

YARD = 0.07                  # points per yard
TD_YARDS = 20                # a touchdown, in yards
TURNOVER_YARDS = 45          # a turnover, in yards
PASSER_SHARE = 0.6           # of a completed pass's value, the part credited to the passer
# defense, in points
TACKLE, SOLO_EXTRA, TFL, SACK_EXTRA, HURRY, PASS_DEFENDED, INTERCEPTION, FUMBLE_RECOVERED, DEF_TD = 0.10, 0.05, 1.0, 0.6, 0.3, 0.7, 3.0, 1.5, 4.0
IN_20 = 0.3                  # a punt downed inside the 20, beyond the average punter's share

REGULAR_GAMES = 0.4          # a regular has played in at least this share of his team's games
# ... and has this much work per team game at his position
WORKLOAD = {"QB": ("att", 10), "RB": ("car", 4), "WR": ("rec", 1.25), "TE": ("rec", 0.75), "DL": ("tkl", 1.25),
            "LB": ("tkl", 2.5), "DB": ("tkl", 1.75), "K": ("kicks", 1.5), "P": ("punts", 1.5)}
MIN_POOL = 8                 # no percentile unless at least this many players qualify

# every number kept for a player: our name, the part of the box score, the name there
FIELDS = [("cmp", "passing", "cmp"), ("att", "passing", "att"), ("pyds", "passing", "yds"), ("ptd", "passing", "td"), ("pint", "passing", "int"),
          ("car", "rushing", "car"), ("ryds", "rushing", "yds"), ("rtd", "rushing", "td"),
          ("rec", "receiving", "rec"), ("recyds", "receiving", "yds"), ("rectd", "receiving", "td"),
          ("fum", "fumbles", "fum"), ("fuml", "fumbles", "lost"), ("fumrec", "fumbles", "rec"),
          ("tkl", "defensive", "tkl"), ("solo", "defensive", "solo"), ("sk", "defensive", "sk"), ("tfl", "defensive", "tfl"),
          ("pd", "defensive", "pd"), ("hur", "defensive", "hur"), ("dtd", "defensive", "td"),
          ("dint", "interceptions", "int"), ("intyds", "interceptions", "yds"),
          ("kr", "kickReturns", "no"), ("kryds", "kickReturns", "yds"), ("krtd", "kickReturns", "td"),
          ("pr", "puntReturns", "no"), ("pryds", "puntReturns", "yds"), ("prtd", "puntReturns", "td"),
          ("fgm", "kicking", "fgm"), ("fga", "kicking", "fga"), ("xpm", "kicking", "xpm"), ("xpa", "kicking", "xpa"),
          ("punts", "punting", "no"), ("puntyds", "punting", "yds"), ("tb", "punting", "tb"), ("in20", "punting", "in20")]
STATS = [f[0] for f in FIELDS]
LONGEST = [("rlong", "rushing", "long"), ("reclong", "receiving", "long"), ("fglong", "kicking", "long"), ("plong", "punting", "long")]
# a game line for a player's card: [game, date, opponent id, opponent, at home, result] and then these
LOG = ["cmp", "att", "pyds", "ptd", "pint", "car", "ryds", "rtd", "rec", "recyds", "rectd", "tkl", "solo", "sk", "tfl", "pd", "dint",
       "fgm", "fga", "xpm", "xpa", "punts", "puntyds"]

# (key, higher is better, who is ranked on it)
METRICS = [
    ("impact_g", True, "all"), ("pass", True, "passes"), ("rush", True, "runs"), ("recv", True, "catches"), ("def", True, "defends"),
    ("st", True, "special"),
    ("pyds_g", True, "passes"), ("cmp_pct", True, "passes"), ("ypa", True, "passes"), ("aya", True, "passes"), ("ptd_pct", True, "passes"),
    ("int_pct", False, "passes"),
    ("ryds_g", True, "runs"), ("ypc", True, "runs"), ("rtd_g", True, "runs"),
    ("rec_g", True, "catches"), ("recyds_g", True, "catches"), ("ypr", True, "catches"), ("share", True, "catches"),
    ("tkl_g", True, "defends"), ("solo_g", True, "defends"), ("tfl_g", True, "defends"), ("sk_g", True, "defends"), ("pd_g", True, "defends"),
    ("plays_g", True, "defends"),
    ("fg_pct", True, "kicks"), ("xp_pct", True, "kicks"), ("kpts_g", True, "kicks"), ("punt_avg", True, "punts"), ("in20_pct", True, "punts"),
]


def _r(v, nd=2):
    return None if v is None else round(v, nd)


def _clean(v):
    return int(v) if v == int(v) else round(v, 1)


def guess_position(p: dict) -> str | None:
    """A player's group from his numbers, when his team's roster does not list him."""
    if p["att"] >= max(5, p["car"], p["rec"]):
        return "QB"
    if p["punts"] and p["punts"] >= p["fga"] + p["xpa"]:
        return "P"
    if p["fga"] + p["xpa"]:
        return "K"
    if p["tkl"] > p["car"] + p["rec"]:
        if p["tfl"] >= 0.15 * p["tkl"] and p["tfl"] >= p["pd"] + 2 * p["dint"]:
            return "DL"
        return "DB" if p["pd"] + p["dint"] > p["tfl"] else "LB"
    if p["rec"] > p["car"]:
        return "WR"
    return "RB" if p["car"] else None


def defense_points(p: dict) -> float:
    return (TACKLE * p["tkl"] + SOLO_EXTRA * p["solo"] + TFL * p["tfl"] + SACK_EXTRA * p["sk"] + HURRY * p["hur"] + PASS_DEFENDED * p["pd"]
            + INTERCEPTION * p["dint"] + YARD * p["intyds"] + FUMBLE_RECOVERED * p["fumrec"] + DEF_TD * p["dtd"])


def compute(ranked: list[dict], games: list[dict], boxes: dict, rosters: dict, logs: dict | None = None) -> dict:
    """Every player with a number in a box score on the given teams (the ranked 25, or all of
    FBS), with totals, rates, impact and percentiles, each measured against the players of
    those teams. `rosters` is {team: {"players": {id: [name, number, position, ...]}}}.
    If `logs` is given it is filled with each player's game-by-game lines, oldest first:
    {player id: [[game, date, opponent id, opponent, at home, result, ...LOG], ...]}."""
    rank = {t["id"]: t for t in ranked if t["id"]}
    players, team_games = {}, {t: 0 for t in rank}
    for g in sorted(games, key=lambda g: (g["date"], g["start"] or 0, g["id"])):
        box = boxes.get(str(g["id"]))
        if g["state"] != "final" or not box:
            continue
        for side, other in (("home", "away"), ("away", "home")):
            team = g[side]["id"]
            cats = (box.get("players") or {}).get(side) or {}
            if team not in rank or not cats:
                continue
            team_games[team] += 1
            team_att = sum(r[3 + CATS["passing"].index("att")] for r in cats.get("passing") or [])
            team_recyds = sum(r[3 + CATS["receiving"].index("yds")] for r in cats.get("receiving") or [])
            lines = {}
            for name, part, col in FIELDS + LONGEST:
                i = 3 + CATS[part].index(col)
                for r in cats.get(part) or []:
                    line = lines.setdefault(r[0], {"name": r[1], "num": r[2]})
                    line[name] = line.get(name, 0) + r[i]
            mine, theirs = g[side].get("score"), g[other].get("score")
            result = "" if mine is None or theirs is None else f"{'W' if mine > theirs else 'L'} {mine}-{theirs}"
            for pid, line in lines.items():
                p = players.setdefault(pid, {"id": pid, "team_id": team, "name": line["name"], "num": line["num"], "gp": 0,
                                             "team_att": 0, "team_recyds": 0, **{s: 0 for s in STATS}, **{k[0]: 0 for k in LONGEST}})
                if p["team_id"] != team:
                    continue                    # the same id on two teams: keep the first
                p["gp"] += 1
                p["team_att"] += team_att
                p["team_recyds"] += team_recyds
                for s in STATS:
                    p[s] += line.get(s, 0)
                for k, _, _ in LONGEST:
                    p[k] = max(p[k], line.get(k, 0))
                if logs is not None:
                    logs.setdefault(pid, []).append([g["id"], g["date"], g[other]["id"], g[other].get("name") or g[other]["id"],
                                                     int(side == "home"), result] + [line.get(s, 0) for s in LOG])

    # who he is: the roster's word first, his numbers otherwise
    for p in players.values():
        listed = ((rosters.get(p["team_id"]) or {}).get("players") or {}).get(p["id"])
        p["pos"] = POS_GROUPS.get(listed[2]) if listed else None
        if listed:
            p["name"], p["num"], p["listed"] = listed[0] or p["name"], listed[1] or p["num"], listed
        if not p["pos"]:
            p["pos"] = guess_position(p)
    everyone = [p for p in players.values() if p["pos"]]
    for p in everyone:
        tg = team_games[p["team_id"]]
        p["kicks"] = p["fga"] + p["xpa"]
        key, need = WORKLOAD[p["pos"]]
        p["regular"] = tg > 0 and p["gp"] >= REGULAR_GAMES * tg and p[key] >= need * tg
        p["air"] = p["pyds"] + TD_YARDS * p["ptd"] - TURNOVER_YARDS * p["pint"]
        p["ground"] = p["ryds"] + TD_YARDS * p["rtd"]
        p["caught"] = p["recyds"] + TD_YARDS * p["rectd"]
        p["stops"] = defense_points(p)

    # What an average regular does: per pass, per carry, per team pass, per game, per kick.
    def rate(group, num, den):
        d = sum(p[den] for p in group)
        return sum(p[num] for p in group) / d if d else 0.0

    regulars = [p for p in everyone if p["regular"]] or everyone
    base = {"any": {"pass": rate([p for p in regulars if p["pos"] == "QB"], "air", "att"), "rush": rate(regulars, "ground", "car"),
                    "fg": rate(everyone, "fgm", "fga"), "xp": rate(everyone, "xpm", "xpa"),
                    "kr": rate(everyone, "kryds", "kr"), "pr": rate(everyone, "pryds", "pr"), "in20": rate(everyone, "in20", "punts")}}
    base["any"]["punt"] = (sum(p["puntyds"] - 20 * p["tb"] for p in everyone) / sum(p["punts"] for p in everyone)) if any(p["punts"] for p in everyone) else 0.0
    for pos in POSITIONS:
        grp = [p for p in regulars if p["pos"] == pos] or [p for p in everyone if p["pos"] == pos]
        base[pos] = {"rush": rate(grp, "ground", "car") if sum(p["car"] for p in grp) >= 50 else base["any"]["rush"],
                     "recv": rate(grp, "caught", "team_att") if pos in ("WR", "TE", "RB") else 0.0,
                     "def": rate(grp, "stops", "gp") if pos in ("DL", "LB", "DB") else 0.0}

    out = []
    for p in everyone:
        b, any_, n = base[p["pos"]], base["any"], p["gp"]
        special = ((p["fgm"] - p["fga"] * any_["fg"]) * 3 + (p["xpm"] - p["xpa"] * any_["xp"])
                   + YARD * ((p["puntyds"] - 20 * p["tb"]) - p["punts"] * any_["punt"]) + IN_20 * (p["in20"] - p["punts"] * any_["in20"])
                   + YARD * ((p["kryds"] + TD_YARDS * p["krtd"]) - p["kr"] * any_["kr"])
                   + YARD * ((p["pryds"] + TD_YARDS * p["prtd"]) - p["pr"] * any_["pr"]))
        part = {"pass": PASSER_SHARE * YARD * (p["air"] - p["att"] * any_["pass"]),
                "rush": YARD * (p["ground"] - p["car"] * b["rush"]),
                "recv": (1 - PASSER_SHARE) * YARD * (p["caught"] - p["team_att"] * b["recv"]) if p["rec"] or b["recv"] else 0.0,
                "def": p["stops"] - n * b["def"],
                "st": special,
                "fum": -YARD * TURNOVER_YARDS * p["fuml"]}
        impact = sum(part.values())
        made = p["tfl"] + p["pd"] + p["dint"] + p["fumrec"]
        v = {"impact_g": impact / n, **{k: part[k] / n for k in PARTS},
             "pyds_g": p["pyds"] / n, "cmp_pct": 100 * p["cmp"] / p["att"] if p["att"] else None, "ypa": p["pyds"] / p["att"] if p["att"] else None,
             "aya": p["air"] / p["att"] if p["att"] else None, "ptd_pct": 100 * p["ptd"] / p["att"] if p["att"] else None,
             "int_pct": 100 * p["pint"] / p["att"] if p["att"] else None,
             "ryds_g": p["ryds"] / n, "ypc": p["ryds"] / p["car"] if p["car"] else None, "rtd_g": p["rtd"] / n,
             "rec_g": p["rec"] / n, "recyds_g": p["recyds"] / n, "ypr": p["recyds"] / p["rec"] if p["rec"] else None,
             "share": 100 * p["recyds"] / p["team_recyds"] if p["team_recyds"] > 0 else None,
             "tkl_g": p["tkl"] / n, "solo_g": p["solo"] / n, "tfl_g": p["tfl"] / n, "sk_g": p["sk"] / n, "pd_g": p["pd"] / n, "plays_g": made / n,
             "fg_pct": 100 * p["fgm"] / p["fga"] if p["fga"] else None, "xp_pct": 100 * p["xpm"] / p["xpa"] if p["xpa"] else None,
             "kpts_g": (3 * p["fgm"] + p["xpm"]) / n if p["kicks"] else None,
             "punt_avg": p["puntyds"] / p["punts"] if p["punts"] else None, "in20_pct": 100 * p["in20"] / p["punts"] if p["punts"] else None}
        can = {"all": True, "passes": p["att"] / n >= 8, "runs": p["car"] / n >= 3, "catches": p["rec"] / n >= 1,
               "defends": p["pos"] in ("DL", "LB", "DB"), "kicks": p["pos"] == "K" and p["kicks"] > 0, "punts": p["pos"] == "P" and p["punts"] > 0,
               "special": p["pos"] in ("K", "P") or (p["kr"] + p["pr"]) / n >= 1}
        t = rank[p["team_id"]]
        row = {"id": p["id"], "name": p["name"], "team": t["name"], "team_id": p["team_id"], "team_rank": t["rank"],
               "num": p["num"] if p["num"] != "" else None, "pos": p["pos"], "gp": n, "regular": p["regular"], "impact": impact,
               "_v": v, "_can": can,
               "tot": {k: v for k, v in {**{s: _clean(p[s]) for s in STATS}, **{k[0]: p[k[0]] for k in LONGEST}}.items() if v}}
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
            "baseline": {"any": {a: _r(b, 4) for a, b in base["any"].items()}, **{k: {a: _r(b, 4) for a, b in base[k].items()} for k in POSITIONS}},
            "weights": {"yard": YARD, "passer_share": PASSER_SHARE, "regular_games": REGULAR_GAMES,
                        "workload": {k: list(v) for k, v in WORKLOAD.items()}}}

"""Rate players against each other, from the box scores.

Impact is runs above average: how many more runs a player has been worth this
season than an average regular in his job would have been in the same playing time.

A hitter's runs come from what he does at the plate, each event at about what
it is worth in runs across the league:
    +0.54 for a single, double or triple (a box score does not say which)
    +1.40 for a home run
    +0.31 for a walk
    -0.26 for an out
and from that is taken what an average regular at his position (catcher,
infielder, outfielder or designated hitter) would have made in the same number
of trips to the plate. It is shown in four parts: hits, home runs, walks and outs.

A pitcher's runs are the earned runs an average regular in his role (starter or
reliever) would have given up while getting the same number of outs, less the
earned runs he gave up himself.

It is a box-score measure. It cannot see fielding or baserunning, it counts a
double the same as a single, and it does not adjust for the ballpark or the opponent.
"""
from __future__ import annotations

from . import config
from .espn import COLS

HITTERS = ["C", "IF", "OF", "DH"]
PITCHERS = ["SP", "RP"]
POSITIONS = HITTERS + PITCHERS
GROUP = {"C": "C", "1B": "IF", "2B": "IF", "3B": "IF", "SS": "IF", "IF": "IF", "LF": "OF", "CF": "OF", "RF": "OF", "OF": "OF",
         "DH": "DH", "SP": "SP", "RP": "RP"}
PARTS = ["hit", "power", "walk", "out"]            # a hitter's; a pitcher's one part is "pit"
W_HIT, W_HR, W_BB, W_OUT = 0.54, 1.40, 0.31, -0.26
MIN_POOL = 8                 # no percentile unless at least this many players qualify

BAT = ["ab", "r", "h", "rbi", "hr", "bb", "k"]
PIT = ["outs", "ph", "pr", "er", "pbb", "pk", "phr", "pc"]
# a game line for a player's card: [game, date, opponent id, opponent, at home, result] and then
# these, and last the pitcher's decision ("W", "L", "S", "H" or "")
LOG = BAT + PIT

# (key, higher is better, whose it is: a hitter's or a pitcher's)
METRICS = [
    ("impact_t", True, "all"), ("hit", True, "bat"), ("power", True, "bat"), ("walk", True, "bat"), ("out", True, "bat"), ("pit", True, "pit"),
    ("impact_g", True, "all"),
    ("avg", True, "bat"), ("obp", True, "bat"), ("slg", True, "bat"), ("ops", True, "bat"), ("hr_rate", True, "bat"),
    ("bb_pct", True, "bat"), ("k_pct", False, "bat"),
    ("era", False, "pit"), ("whip", False, "pit"), ("k9", True, "pit"), ("bb9", False, "pit"), ("hr9", False, "pit"), ("kbb", True, "pit"), ("ip_g", True, "pit"),
]


def _r(v, nd=2):
    return None if v is None else round(v, nd)


def group(position: str) -> str | None:
    """Which of the six jobs a position is: "SS" is an infielder, "CF" an outfielder."""
    return GROUP.get((position or "").upper())


def innings(outs: int) -> str:
    """Outs as innings pitched, the way a box score writes them: 20 outs is "6.2"."""
    return f"{outs // 3}.{outs % 3}"


def batting_parts(p: dict) -> dict:
    """What a batting line is worth in runs, in its four parts."""
    return {"hit": W_HIT * (p["h"] - p["hr"]), "power": W_HR * p["hr"], "walk": W_BB * p["bb"], "out": W_OUT * (p["ab"] - p["h"])}


def compute(ranked: list[dict], games: list[dict], boxes: dict, rosters: dict, logs: dict | None = None) -> dict:
    """Every player who has got into a game for the given teams, with totals, rates, impact
    and percentiles, each measured against the players of those teams. `rosters` is
    {team: {"players": {id: [name, number, position, ...]}}}. Only the regular season
    counts; playoff games are listed but left out of the season's numbers. If `logs` is
    given it is filled with each player's game-by-game lines, oldest first:
    {player id: [[game, date, opponent id, opponent, at home, result, ...LOG, decision], ...]}."""
    rank = {t["id"]: t for t in ranked if t["id"]}
    players, team_games = {}, {t: 0 for t in rank}
    at = {c: 5 + i for i, c in enumerate(COLS)}
    for g in sorted(games, key=lambda g: (g["date"], g["start"] or 0, g["id"])):
        box = boxes.get(str(g["id"]))
        if g["state"] != "final" or not box or g.get("kind", 2) != 2:
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
                batted, pitched = r[at["bo"]] > 0 or r[at["ab"]] + r[at["bb"]] > 0, r[at["pn"]] > 0
                p = players.setdefault(r[0], {"id": r[0], "team_id": team, "name": r[1], "box_pos": {}, "gp": 0, "g": 0, "gs": 0, "gp_p": 0, "gs_p": 0,
                                              "w": 0, "l": 0, "sv": 0, "hld": 0, "avg": None, "obp": None, "slg": None, "era": None,
                                              **{s: 0 for s in BAT + PIT}})
                p["team_id"] = team                # traded in mid-season: his numbers go with him to his newest team
                p["gp"] += 1
                if r[3] and r[3] not in ("PH", "PR", "P"):
                    p["box_pos"][r[3]] = p["box_pos"].get(r[3], 0) + 1
                if batted:
                    p["g"] += 1
                    p["gs"] += 1 if r[4] and not (pitched and r[at["pn"]] == 1 and r[at["bo"]] == 0) else 0
                    for s in BAT:
                        p[s] += r[at[s]]
                    if r[at["ab"]] + r[at["bb"]] > 0:
                        # his season's figures, as of his latest game
                        p["avg"], p["obp"], p["slg"] = r[at["avg"]] / 1000, r[at["obp"]] / 1000, r[at["slg"]] / 1000
                if pitched:
                    p["gp_p"] += 1
                    p["gs_p"] += 1 if r[at["pn"]] == 1 else 0
                    for s in PIT:
                        p[s] += r[at[s]]
                    p["era"] = r[at["era"]] / 100
                    key = {"W": "w", "L": "l", "S": "sv", "H": "hld"}.get(r[2])
                    if key:
                        p[key] += 1
                if logs is not None:
                    logs.setdefault(r[0], []).append([g["id"], g["date"], g[other]["id"], g[other].get("name") or g[other]["id"],
                                                     int(side == "home"), result] + [r[at[s]] for s in LOG] + [r[2]])

    # what he is: the roster's word first, the box scores' otherwise
    for p in players.values():
        listed = ((rosters.get(p["team_id"]) or {}).get("players") or {}).get(p["id"])
        p["pos"] = (listed[2] if listed else "") or ""
        if listed:
            p["name"], p["listed"] = listed[0] or p["name"], listed
        if not group(p["pos"]) and p["box_pos"]:
            p["pos"] = max(p["box_pos"], key=p["box_pos"].get)
        if p["pos"] in ("SP", "RP", "P", "") and p["gp_p"]:
            p["pos"] = "SP" if 2 * p["gs_p"] >= p["gp_p"] else "RP"         # by how he has been used
        p["group"] = group(p["pos"]) or ("RP" if p["gp_p"] and not p["ab"] else "IF")
        p["pa"] = p["ab"] + p["bb"]
    everyone = list(players.values())
    for p in everyone:
        tg = team_games[p["team_id"]]
        if p["group"] in PITCHERS:
            need = config.REGULAR_OUTS_SP if p["group"] == "SP" else config.REGULAR_OUTS_RP
            p["regular"] = tg > 0 and p["outs"] >= need * tg
        else:
            p["regular"] = tg > 0 and p["pa"] >= config.REGULAR_PA * tg
        p["parts"] = batting_parts(p)

    # What an average regular makes: a hitter per trip to the plate, part by part, at each
    # position; a pitcher in earned runs per out, as a starter and as a reliever.
    hitters = [p for p in everyone if p["group"] in HITTERS and p["pa"]]
    pitchers = [p for p in everyone if p["group"] in PITCHERS and p["outs"]]
    reg_h = [p for p in hitters if p["regular"]] or hitters
    reg_p = [p for p in pitchers if p["regular"]] or pitchers

    def bat_base(grp):
        pa = sum(p["pa"] for p in grp)
        return {k: (sum(p["parts"][k] for p in grp) / pa if pa else 0.0) for k in PARTS}

    def pit_base(grp):
        outs = sum(p["outs"] for p in grp)
        return sum(p["er"] for p in grp) / outs if outs else 0.0

    base = {"H": bat_base(reg_h), "P": pit_base(reg_p)}
    for pos in HITTERS:
        grp = [p for p in reg_h if p["group"] == pos]
        base[pos] = bat_base(grp) if len(grp) >= MIN_POOL else base["H"]
    for pos in PITCHERS:
        grp = [p for p in reg_p if p["group"] == pos]
        base[pos] = pit_base(grp) if len(grp) >= MIN_POOL else base["P"]

    out = []
    for p in everyone:
        is_p = p["group"] in PITCHERS
        n, pa, outs = p["gp"], p["pa"], p["outs"]
        part = {k: None for k in PARTS}
        pit = None
        if pa and not (is_p and pa < 20):                # a pitcher's rare trips to the plate are left out
            b = base[p["group"]] if not is_p else base["H"]
            part = {k: p["parts"][k] - pa * b[k] for k in PARTS}
        if outs:
            rate = base[p["group"]] if is_p else base["RP"]            # a position player on the mound is measured as a reliever
            pit = rate * outs - p["er"]
        impact = sum(x for x in part.values() if x is not None) + (pit or 0.0)
        ip = outs / 3
        obp, slg = p["obp"], p["slg"]
        v = {"impact_t": impact, **part, "pit": pit, "impact_g": impact / n,
             "avg": p["avg"] if pa else None, "obp": obp if pa else None, "slg": slg if pa else None,
             "ops": obp + slg if pa and obp is not None and slg is not None else None,
             "hr_rate": 600 * p["hr"] / pa if pa else None, "bb_pct": 100 * p["bb"] / pa if pa else None, "k_pct": 100 * p["k"] / pa if pa else None,
             "era": (p["era"] if p["era"] is not None else 9 * p["er"] / ip) if outs else None, "whip": (p["ph"] + p["pbb"]) / ip if outs else None,
             "k9": 9 * p["pk"] / ip if outs else None, "bb9": 9 * p["pbb"] / ip if outs else None, "hr9": 9 * p["phr"] / ip if outs else None,
             "kbb": p["pk"] / p["pbb"] if p["pbb"] else None, "ip_g": ip / p["gp_p"] if p["gp_p"] else None}
        can = {"all": True, "bat": not is_p and pa > 0, "pit": is_p and outs > 0}
        t = rank[p["team_id"]]
        tot = {s: p[s] for s in ["g", "gs"] + BAT + ["gp_p", "gs_p"] + PIT + ["w", "l", "sv", "hld"] if p[s]}
        row = {"id": p["id"], "name": p["name"], "team": t["name"], "team_id": p["team_id"], "team_rank": t["rank"],
               "num": None, "pos": p["pos"], "group": p["group"], "gp": n, "regular": p["regular"], "impact": impact,
               "_v": v, "_can": can, "tot": tot}
        listed = p.get("listed")
        if listed:
            row["num"] = listed[1] if listed[1] != "" else None
            bio = {}
            if listed[3]:
                bio["ht"] = f"{listed[3] // 12}-{listed[3] % 12}"
            if listed[4]:
                bio["wt"] = listed[4]
            if len(listed) > 8 and listed[8]:
                bio["bt"] = "Bats/throws " + listed[8]
            if listed[5]:
                bio["yr"] = listed[5]
            if listed[6]:
                bio["home"] = listed[6]
            if bio:
                row["bio"] = bio
            if listed[7] and config.SHOW_PHOTOS:
                row["ph"] = 1                   # he has a photo: the page builds its address from his id
        out.append(row)

    # Percentiles: against regulars in the same job. (With too few of them, as can happen with
    # designated hitters, against every regular hitter.)
    keys = [m[0] for m in METRICS]
    for pos in POSITIONS:
        mine = [q for q in out if q["group"] == pos and q["regular"]]
        wider = [q for q in out if q["regular"] and (q["group"] in HITTERS) == (pos in HITTERS)]
        for key, higher, who in METRICS:
            pool = [q for q in (mine if len(mine) >= MIN_POOL else wider) if q["_can"][who] and q["_v"][key] is not None]
            if len(pool) < MIN_POOL:
                continue
            vals = sorted(q["_v"][key] for q in pool)
            for q in pool:
                if q["group"] != pos:
                    continue
                x = q["_v"][key]
                below = sum(1 for y in vals if y < x) + 0.5 * sum(1 for y in vals if y == x)
                pct = 100 * below / len(vals)
                q.setdefault("_pct", {})[key] = int(min(99, max(1, round(pct if higher else 100 - pct))))

    # Ranks: by Impact for the season among regulars, overall and in the same job.
    ordered = sorted((q for q in out if q["regular"]), key=lambda q: (-q["impact"], q["name"]))
    seen = {}
    for i, q in enumerate(ordered):
        q["rank"] = i + 1
        seen[q["group"]] = seen.get(q["group"], 0) + 1
        q["pos_rank"] = seen[q["group"]]
    rows = []
    for q in sorted(out, key=lambda q: (q.get("rank") or 10**6, -q["impact"])):
        row = {k: q[k] for k in ("id", "name", "team", "team_id", "team_rank", "num", "pos", "group", "gp", "regular", "tot")}
        row.update(rank=q.get("rank"), pos_rank=q.get("pos_rank"), impact=_r(q["impact"], 1),
                   v=[_r(q["_v"][k], 3 if k in ("avg", "obp", "slg", "ops") else 2) for k in keys])
        if q.get("_pct"):
            row["pct"] = [q["_pct"].get(k) for k in keys]       # percentiles, for regulars only
        for extra in ("bio", "ph"):
            if extra in q:
                row[extra] = q[extra]
        rows.append(row)
    return {"metrics": keys, "players": rows, "regulars": len(ordered), "pos_regulars": seen,
            "teams": [{"id": t, "name": rank[t]["name"], "rank": rank[t]["rank"], "games": team_games[t]}
                      for t in sorted(rank, key=lambda t: (rank[t]["rank"] is None, rank[t]["rank"] or 0, rank[t]["name"]))],
            "baseline": {"bat": {k: {a: _r(b, 4) for a, b in base[k].items()} for k in HITTERS}, "pit": {k: _r(9 * 3 * base[k], 2) for k in PITCHERS}},
            "weights": {"hit": W_HIT, "hr": W_HR, "bb": W_BB, "out": W_OUT, "regular_pa": config.REGULAR_PA,
                        "regular_outs_sp": config.REGULAR_OUTS_SP, "regular_outs_rp": config.REGULAR_OUTS_RP}}

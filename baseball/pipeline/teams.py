"""Team stats, from the box scores.

Each team's hitting (batting average, on-base percentage, slugging and the two
added together, home runs and steals) and its pitching and fielding (earned run
average, baserunners allowed per inning, strikeouts and walks per nine innings,
errors), with runs scored and allowed per game.
"""
from __future__ import annotations

from . import config
from .espn import TEAM

I = {c: i for i, c in enumerate(TEAM)}


def compute(ranked: list[dict], games: list[dict], boxes: dict, rating: dict, info: dict | None = None, conf_key: str = "conf") -> dict:
    """{"teams": [...], "through": date}. `games` are the season's games of the
    teams given; `rating` is every team's rating from pipeline/odds.py; `info`
    is {team: {"conf", "rec"}} from the standings, and `conf_key` says which of
    its records goes beside the division's name."""
    rank = {t["id"]: t for t in ranked if t.get("id")}
    info = info or {}
    power = {t: i + 1 for i, t in enumerate(sorted((t for t in rating if not info or t in info), key=lambda x: -rating[x]))}
    acc = {t: {"w": 0, "l": 0, "pf": 0, "pa": 0, "n": 0, "bpf": 0, "bpa": 0, "opp_r": [], "own": [0] * len(TEAM), "opp": [0] * len(TEAM)} for t in rank}
    through = None
    counted = (2,)                                          # the playoffs are left out of the season's numbers
    for g in games:
        if g["state"] != "final" or g["away"].get("score") is None or g["home"].get("score") is None or g.get("kind", 2) not in counted:
            continue
        through = max(through or g["date"], g["date"])
        team = (boxes.get(str(g["id"])) or {}).get("team") or {}
        for side, other in (("home", "away"), ("away", "home")):
            t = g[side]["id"]
            if t not in acc:
                continue
            a, mine, theirs = acc[t], g[side]["score"], g[other]["score"]
            a["w" if mine > theirs else "l"] += 1
            a["pf"] += mine
            a["pa"] += theirs
            if g[other]["id"] in rating:
                a["opp_r"].append(rating[g[other]["id"]])
            if team.get(side) and team.get(other):            # stats only from games with a box score
                a["n"] += 1
                a["bpf"] += mine
                a["bpa"] += theirs
                for i in range(len(TEAM)):
                    a["own"][i] += team[side][i]
                    a["opp"][i] += team[other][i]
    out = []
    for t, a in acc.items():
        o = dict(zip(TEAM, a["own"]))
        p = dict(zip(TEAM, a["opp"]))
        n, played = a["n"], a["w"] + a["l"]

        def per(x, nd=2):
            return round(x / n, nd) if n else None

        def ratio(x, y, nd=3, scale=1.0):
            return round(scale * x / y, nd) if y else None

        obp, slg = ratio(o["h"] + o["bb"] + o["hbp"], o["ab"] + o["bb"] + o["hbp"] + o["sf"]), ratio(o["tb"], o["ab"])
        out.append({
            "id": t, "name": rank[t]["name"], "rank": rank[t]["rank"], "conf": (info.get(t) or {}).get("conf") or "",
            "conf_rec": ((info.get(t) or {}).get("rec") or {}).get(conf_key) or "", "w": a["w"], "l": a["l"], "games": n,
            "rpg": round(a["pf"] / played, 2) if played else None, "rapg": round(a["pa"] / played, 2) if played else None,
            "diff": a["pf"] - a["pa"] if played else None,
            "avg": ratio(o["h"], o["ab"]), "obp": obp, "slg": slg, "ops": round(obp + slg, 3) if obp is not None and slg is not None else None,
            "hr_g": per(o["hr"]), "sb_g": per(o["sb"]), "bb_g": per(o["bb"]), "k_g": per(o["k"]),
            "era": ratio(o["er"], o["outs"], 2, 27.0), "whip": ratio(o["ph"] + o["pbb"], o["outs"], 2, 3.0),
            "k9": ratio(o["pk"], o["outs"], 1, 27.0), "bb9": ratio(o["pbb"], o["outs"], 1, 27.0), "hr9": ratio(o["phr"], o["outs"], 2, 27.0),
            "opp_avg": ratio(o["ph"], p["ab"]), "e_g": per(o["e"]),
            "power": power.get(t), "sos": round(sum(a["opp_r"]) / len(a["opp_r"]), 3) if a["opp_r"] else None,
        })
    # strength of schedule as a rank among the teams given: 1 is the hardest
    for i, r in enumerate(sorted((r for r in out if r["sos"] is not None), key=lambda r: -r["sos"])):
        r["sos_rank"] = i + 1
    for r in out:
        r.pop("sos")
    out.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["name"]))
    return {"teams": out, "through": through}

"""Team stats, from the box scores.

Each team's own numbers per game and its opponents' numbers against it, plus
the site's rating of the team (the one behind the odds) and how hard its
schedule has been (the average rating of the teams it has played).
"""
from __future__ import annotations

from .espn import TEAM

I = {c: i for i, c in enumerate(TEAM)}


def compute(ranked: list[dict], games: list[dict], boxes: dict, rating: dict, info: dict | None = None) -> dict:
    """{"teams": [...], "through": date}. `games` are the season's games of the
    teams given; `rating` is every team's rating from pipeline/odds.py; `info`
    is {team: {"conf", "rec"}} from the conference standings."""
    rank = {t["id"]: t for t in ranked if t.get("id")}
    info = info or {}
    power = {t: i + 1 for i, t in enumerate(sorted((t for t in rating if not info or t in info), key=lambda x: -rating[x]))}
    acc = {t: {"w": 0, "l": 0, "pf": 0, "pa": 0, "n": 0, "bpf": 0, "bpa": 0, "opp_r": [], "own": [0] * len(TEAM), "opp": [0] * len(TEAM)} for t in rank}
    through = None
    for g in games:
        if g["state"] != "final" or g["away"].get("score") is None or g["home"].get("score") is None:
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

        def per(x, nd=1):
            return round(x / n, nd) if n else None

        def ratio(x, y, nd=2, scale=1.0):
            return round(scale * x / y, nd) if y else None

        out.append({
            "id": t, "name": rank[t]["name"], "rank": rank[t]["rank"], "conf": (info.get(t) or {}).get("conf") or "",
            "conf_rec": ((info.get(t) or {}).get("rec") or {}).get("conf") or "", "w": a["w"], "l": a["l"], "games": n,
            "ppg": round(a["pf"] / played, 1) if played else None, "opp_ppg": round(a["pa"] / played, 1) if played else None,
            "margin": round((a["pf"] - a["pa"]) / played, 1) if played else None,
            "ypp": ratio(o["yds"], o["att"] + o["car"]), "opp_ypp": ratio(p["yds"], p["att"] + p["car"]),
            "yds_g": per(o["yds"]), "opp_yds_g": per(p["yds"]), "pass_g": per(o["pyds"]), "rush_g": per(o["ryds"]),
            "opp_pass_g": per(p["pyds"]), "opp_rush_g": per(p["ryds"]),
            "third": ratio(o["c3"], o["a3"], 1, 100.0), "opp_third": ratio(p["c3"], p["a3"], 1, 100.0),
            "to_margin": per(p["to"] - o["to"], 2), "pen_g": per(o["penyds"]),
            "ppd": ratio(a["bpf"], o["drives"]), "opp_ppd": ratio(a["bpa"], p["drives"]),
            "power": power.get(t), "sos": round(sum(a["opp_r"]) / len(a["opp_r"]), 3) if a["opp_r"] else None,
        })
    # strength of schedule as a rank among the teams given: 1 is the hardest
    for i, r in enumerate(sorted((r for r in out if r["sos"] is not None), key=lambda r: -r["sos"])):
        r["sos_rank"] = i + 1
    for r in out:
        r.pop("sos")
    out.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["name"]))
    return {"teams": out, "through": through}

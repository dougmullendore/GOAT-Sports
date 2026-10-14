"""Team stats, from the box scores.

Each team's scoring and shooting, and the "four factors" that decide most
games: shooting (effective field goal percentage, which counts a three as one
and a half baskets), turnovers, offensive rebounding and getting to the line.
Offense and defense are also given per 100 possessions, so a fast team and a
slow one can be compared; a possession is counted as a shot that is not
rebounded by the offense, a turnover, or a trip to the line
(field goals tried - offensive rebounds + turnovers + 0.44 x free throws tried).
"""
from __future__ import annotations

from . import config
from .espn import TEAM

I = {c: i for i, c in enumerate(TEAM)}


def possessions(t: dict) -> float:
    return t["fga"] - t["oreb"] + t["to"] + 0.44 * t["fta"]


def compute(ranked: list[dict], games: list[dict], boxes: dict, rating: dict, info: dict | None = None, conf_key: str = "conf",
            kinds: tuple | None = None) -> dict:
    """{"teams": [...], "through": date}. `games` are the season's games of the
    teams given; `rating` is every team's rating from pipeline/odds.py; `info`
    is {team: {"conf", "rec"}} from the standings, and `conf_key` says which of
    its records goes beside the conference's name ("div" for the NBA, whose
    teams are grouped by division)."""
    rank = {t["id"]: t for t in ranked if t.get("id")}
    info = info or {}
    power = {t: i + 1 for i, t in enumerate(sorted((t for t in rating if not info or t in info), key=lambda x: -rating[x]))}
    acc = {t: {"w": 0, "l": 0, "pf": 0, "pa": 0, "n": 0, "bpf": 0, "bpa": 0, "opp_r": [], "own": [0] * len(TEAM), "opp": [0] * len(TEAM)} for t in rank}
    through = None
    counted = kinds or ((2, 3) if config.POLL_TYPE else (2,))          # the NBA's playoffs are left out of the season's numbers;
    # `kinds` (1,) counts the NBA's warm-up games instead, while they are all there is
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
        poss = (possessions(o) + possessions(p)) / 2 if n else 0.0

        def per(x, nd=1):
            return round(x / n, nd) if n else None

        def ratio(x, y, nd=1, scale=100.0):
            return round(scale * x / y, nd) if y else None

        ortg, drtg = ratio(a["bpf"], poss), ratio(a["bpa"], poss)
        out.append({
            "id": t, "name": rank[t]["name"], "rank": rank[t]["rank"], "conf": (info.get(t) or {}).get("conf") or "",
            "conf_rec": ((info.get(t) or {}).get("rec") or {}).get(conf_key) or "", "w": a["w"], "l": a["l"], "games": n,
            "ppg": round(a["pf"] / played, 1) if played else None, "opp_ppg": round(a["pa"] / played, 1) if played else None,
            "margin": round((a["pf"] - a["pa"]) / played, 1) if played else None,
            "ortg": ortg, "drtg": drtg, "net": round(ortg - drtg, 1) if ortg is not None and drtg is not None else None,
            "pace": per(poss), "fg_pct": ratio(o["fgm"], o["fga"]), "tp_pct": ratio(o["tpm"], o["tpa"]), "ft_pct": ratio(o["ftm"], o["fta"]),
            "efg": ratio(o["fgm"] + 0.5 * o["tpm"], o["fga"]), "opp_efg": ratio(p["fgm"] + 0.5 * p["tpm"], p["fga"]),
            "tov": ratio(o["to"], possessions(o)), "opp_tov": ratio(p["to"], possessions(p)),
            "orb": ratio(o["oreb"], o["oreb"] + p["dreb"]), "ftr": ratio(o["fta"], o["fga"]),
            "reb_g": per(o["reb"]), "ast_g": per(o["ast"]), "stl_g": per(o["stl"]), "blk_g": per(o["blk"]), "to_g": per(o["to"]),
            "tp_g": per(o["tpm"]),
            "power": power.get(t), "sos": round(sum(a["opp_r"]) / len(a["opp_r"]), 3) if a["opp_r"] else None,
        })
    # strength of schedule as a rank among the teams given: 1 is the hardest
    for i, r in enumerate(sorted((r for r in out if r["sos"] is not None), key=lambda r: -r["sos"])):
        r["sos_rank"] = i + 1
    for r in out:
        r.pop("sos")
    out.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["name"]))
    return {"teams": out, "through": through}

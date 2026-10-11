"""The GOAT ranking: the site's own order of the 32 teams, worked out the same
way as on every other GOAT site.

Head to head comes first: a team that has the better of another is ranked
above it where that can be done without contradicting more results than it
honors. Behind that is a score made of four things:
  1. who it beat (GOAT_WEIGHTS[0]): every win adds the quality of the team
     beaten, squared, and every loss takes away a quarter (GOAT_LOSS) plus
     three quarters of how weak the team lost to was, squared. A team's quality is its place among the 32 by the ratings behind
     the odds, 0 for the weakest and 1 for the strongest. So a win over a top
     team is worth far more than one over a weak team, and a loss to a weak
     team costs far more than one to a top team. The totals are stretched to
     run from 0 (the lowest) to 1 (the highest);
  2. how good it is (GOAT_WEIGHTS[1]): its own rating, the one behind the odds,
     stretched to run from 0 for the lowest-rated team to 1 for the highest;
  3. record (GOAT_WEIGHTS[2]): its share of games won, an overtime or shootout
     loss counting as a loss;
  4. the standings (GOAT_WEIGHTS[3]): credit for its place in them.

The order starts from that score. Then every pair of teams has a price for
being ranked the "wrong" way round: ranking a team above one that has the
better of it costs 1 for each win the other is ahead by, and ranking it above
a team with a higher score costs the gap divided by GOAT_HEAD_TO_HEAD. The
GOAT order is the one with the lowest total price. Regular season only.

Strength of schedule, expected-goal share and goal share are still worked out
here, for the columns beside the ranking; they no longer decide it.
"""
from __future__ import annotations

import bisect

from . import config


def head_to_head(games: list[dict]) -> dict:
    """{(team, opponent): [wins, losses, [dates won]]} from finished games."""
    out = {}
    for g in sorted(games, key=lambda g: (g["date"], g["id"])):
        hs, vs = g["home"].get("score"), g["away"].get("score")
        if g["state"] != "final" or hs is None or vs is None or hs == vs:
            continue
        w, l = (g["home"]["id"], g["away"]["id"]) if hs > vs else (g["away"]["id"], g["home"]["id"])
        a = out.setdefault((w, l), [0, 0, []])
        a[0] += 1
        a[2].append(g["date"])
        out.setdefault((l, w), [0, 0, []])[1] += 1
    return out


def _percentile(values: dict) -> dict:
    """Each value's place among all of them, 0 (lowest) to 1 (highest); ties share."""
    xs = sorted(values.values())
    n = len(xs) or 1
    return {k: (bisect.bisect_left(xs, v) + 0.5 * (bisect.bisect_right(xs, v) - bisect.bisect_left(xs, v))) / n
            for k, v in values.items()}


def order_teams(games: list[dict], rating: dict, teams: set, in_poll: dict) -> dict:
    """Rank `teams` (ids). `in_poll` is {id: poll rank} for the ranked teams.
    Returns {"order": [ids, best first], "base": {id: place by score alone},
    "score": {id: score}, "factors": {id: [who it beat, poll, record]}}."""
    finals = [g for g in games if g["state"] == "final" and g["home"].get("score") is not None
              and g["away"].get("score") is not None and g["home"]["score"] != g["away"]["score"]]
    floor = min(rating.values()) if rating else 0.0
    # how good each team is, from 0 (the weakest) to 1 (the strongest), by the ratings behind the odds;
    # a school from outside the division counts as the weakest
    quality = _percentile({t: rating.get(t, floor) for t in teams})
    won, played, earned = {}, {}, {}
    for g in finals:
        for side, other in (("home", "away"), ("away", "home")):
            t = g[side]["id"]
            if t not in teams:
                continue
            q = quality.get(g[other]["id"], 0.0)
            win = g[side]["score"] > g[other]["score"]
            played[t] = played.get(t, 0) + 1
            won[t] = won.get(t, 0) + win
            # who it beat: a win is worth more the better the team beaten, a loss costs more the worse the team lost to
            earned[t] = earned.get(t, 0.0) + (q ** config.GOAT_CURVE if win else -(config.GOAT_LOSS + (1 - config.GOAT_LOSS) * (1 - q) ** config.GOAT_CURVE))
    lo, hi = min((earned.get(t, 0.0) for t in teams), default=0.0), max((earned.get(t, 0.0) for t in teams), default=0.0)
    beat = {t: (earned.get(t, 0.0) - lo) / (hi - lo) if hi > lo else 0.0 for t in teams}
    rec = {t: won.get(t, 0) / played[t] if played.get(t) else 0.0 for t in teams}
    size = max(in_poll.values(), default=25)        # 25 for a poll; the number of teams in a league numbered by its standings
    poll = {t: (size + 1 - in_poll[t]) / size if t in in_poll else 0.0 for t in teams}
    # how good it is: its own rating (which follows the margins it wins and loses by, and who against),
    # stretched to run from 0 for the lowest-rated team to 1 for the highest
    low, high = min((rating.get(t, floor) for t in teams), default=0.0), max((rating.get(t, floor) for t in teams), default=0.0)
    power = {t: (rating.get(t, floor) - low) / (high - low) if high > low else 0.0 for t in teams}
    wb, wg, wr, wp = config.GOAT_WEIGHTS
    score = {t: wb * beat[t] + wg * power[t] + wr * rec[t] + wp * poll[t] for t in teams}
    # before anyone has played, every score is level: the ratings carried over from last season decide
    order = sorted(teams, key=lambda t: (-score[t], -rating.get(t, floor), t))
    base = {t: i + 1 for i, t in enumerate(order)}
    net = {(a, b): x[0] - x[1] for (a, b), x in head_to_head(finals).items()
           if a in teams and b in teams and x[0] > x[1]}

    def price(a, b):                       # what it costs to rank a above b
        return net.get((b, a), 0) + max(0.0, score[b] - score[a]) / config.GOAT_HEAD_TO_HEAD

    # Moves look this far up and down the order: far enough for any result
    # that could matter, near enough to stay quick with every team.
    reach, moved, rounds = config.GOAT_REACH, True, 0
    while moved and rounds < 500:
        moved, rounds = False, rounds + 1
        for src in range(len(order)):
            x, best, d = order[src], (-1e-9, None), 0.0
            for dst in range(src - 1, max(-1, src - reach - 1), -1):
                t = order[dst]
                d += price(x, t) - price(t, x)
                if d < best[0]:
                    best = (d, dst)
            d = 0.0
            for dst in range(src + 1, min(len(order), src + reach + 1)):
                t = order[dst]
                d += price(t, x) - price(x, t)
                if d < best[0]:
                    best = (d, dst)
            if best[1] is not None:
                order.pop(src)
                order.insert(best[1], x)
                moved = True
    # The top 25 are always the poll's 25 teams, in this ranking's order among
    # themselves; every other team follows from 26, in its order here.
    order = [t for t in order if t in in_poll] + [t for t in order if t not in in_poll]
    return {"order": order, "base": base, "score": score,
            "factors": {t: [round(beat[t], 3), round(poll[t], 3), round(rec[t], 3), round(power[t], 3)] for t in teams}}


def contradictions(order: list, games: list[dict], among: set) -> int:
    """How many head-to-head results between teams in `among` the order gets
    the wrong way round (a team ranked below one it has the better of)."""
    place = {t: i for i, t in enumerate(order)}
    return sum(1 for (a, b), (wins, losses, _) in head_to_head(games).items()
               if a in among and b in among and a in place and b in place and wins > losses and place[a] > place[b])


def played(games: list[dict]) -> list[dict]:
    return [g for g in sorted(games, key=lambda g: (g["date"], g["start"] or 0, g["id"]))
            if g["state"] == "final" and g["home"].get("score") is not None and g["away"].get("score") is not None
            and g["home"]["score"] != g["away"]["score"]]


def rank(games: list[dict], rating: dict, table: list[dict], xg: dict) -> dict:
    """Rank the teams in `table` (the standings rows). `games` are the games
    that count; `rating` is every team's rating from pipeline/odds.py; `xg` is
    {team: [expected goals for, against]} over the games with play-by-play.
    Returns {"order": [ids, best first], "score": {id: score}, "factors": {id: [who it beat,
    standings, record]}, and per team "sos", "xg_pct" and "goal_pct" (the raw numbers)}."""
    teams = [t["id"] for t in table]
    floor = min(rating.values()) if rating else 0.0
    opp, gf, ga = {t: [] for t in teams}, dict.fromkeys(teams, 0), dict.fromkeys(teams, 0)
    done = played(games)
    for g in done:
        shootout = g.get("end") == "SO"
        for side, other in (("home", "away"), ("away", "home")):
            t = g[side]["id"]
            if t not in opp:
                continue
            mine, theirs = g[side]["score"], g[other]["score"]
            opp[t].append(rating.get(g[other]["id"], floor))
            gf[t] += mine - (1 if shootout and mine > theirs else 0)
            ga[t] += theirs - (1 if shootout and theirs > mine else 0)
    sos = {t: sum(opp[t]) / len(opp[t]) if opp[t] else 0.0 for t in teams}
    goal_pct = {t: gf[t] / (gf[t] + ga[t]) if gf[t] + ga[t] else 0.5 for t in teams}
    xg_pct = {t: xg[t][0] / (xg[t][0] + xg[t][1]) if t in xg and xg[t][0] + xg[t][1] > 0 else 0.5 for t in teams}
    # before the first game the standings are only a list, so they give no credit and the ratings decide
    standing = {t["id"]: t["rank"] for t in table if t.get("rank")} if done else {}
    out = order_teams(done, rating, set(teams), standing if len(standing) == len(teams) else {})
    return {**out, "sos": sos, "xg_pct": xg_pct, "goal_pct": goal_pct}

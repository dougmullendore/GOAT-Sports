"""The GOAT ranking: the site's own order of every team in the league (every Division I team; every NBA team).

Four things decide it:
  1. the poll, half the score (GOAT_WEIGHTS[0]): the AP poll for college, (26 - rank) / 25
     for a ranked team and 0 otherwise; for the NBA, ESPN's newest power
     ranking (pipeline/power.py), or the standings until one has been read;
  2. strength of schedule (GOAT_WEIGHTS[1]): the average rating of the teams it
     has played (the ratings behind the odds), stretched to run from 0 for the
     easiest schedule to 1 for the hardest;
  3. strength of record (GOAT_WEIGHTS[2]): every win adds the quality of the
     team beaten, raised to GOAT_CURVE, and every loss takes away GOAT_LOSS
     plus the rest of 1 times how weak the team lost to was, raised to
     GOAT_CURVE. A team's quality is its place among all the teams by the
     ratings, 0 for the weakest and 1 for the strongest; a team from outside
     the division counts as the weakest. So a win over a top team is worth far
     more than a win over a weak one, a loss to a weak team costs far more
     than a loss to a top one, and no loss is free. The totals are stretched
     to run from 0 (the lowest) to 1 (the highest);
  4. head to head, the last tenth (GOAT_HEAD_TO_HEAD): a team that has the
     better of another is ranked above it when the two are within that much
     of each other on the first three.
The same formula is used on every GOAT site.

The order starts from the score of the first three. Then every pair of teams
has a price for being ranked the "wrong" way round: ranking a team above one
that has the better of it head to head costs 1 (however many games the lead is
by), and ranking it above a team with a higher score costs the gap divided by
GOAT_HEAD_TO_HEAD. The GOAT order is the one with the lowest total price, found
by moving one team at a time to wherever it lowers the total most, until no
move helps. Results that form a circle (A beat B, B beat C, C beat A) cannot
all be honored; it keeps as many as it can.
"""
from __future__ import annotations

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
    import bisect
    return {k: (bisect.bisect_left(xs, v) + 0.5 * (bisect.bisect_right(xs, v) - bisect.bisect_left(xs, v))) / n
            for k, v in values.items()}


def rank(games: list[dict], rating: dict, teams: set, in_poll: dict) -> dict:
    """Rank `teams` (ids). `in_poll` is {id: poll rank} for the ranked teams.
    Returns {"order": [ids, best first], "base": {id: place by score alone},
    "score": {id: score}, "factors": {id: [strength of record, poll, share of games won, strength of schedule]}}."""
    finals = [g for g in games if g["state"] == "final" and g["home"].get("score") is not None
              and g["away"].get("score") is not None and g["home"]["score"] != g["away"]["score"]]
    floor = min(rating.values()) if rating else 0.0
    # how good each team is, from 0 (the weakest) to 1 (the strongest), by the ratings behind the odds;
    # a school from outside the division counts as the weakest
    quality = _percentile({t: rating.get(t, floor) for t in teams})
    won, played, earned, faced = {}, {}, {}, {}
    for g in finals:
        for side, other in (("home", "away"), ("away", "home")):
            t = g[side]["id"]
            if t not in teams:
                continue
            q = quality.get(g[other]["id"], 0.0)
            win = g[side]["score"] > g[other]["score"]
            played[t] = played.get(t, 0) + 1
            faced.setdefault(t, []).append(rating.get(g[other]["id"], floor))
            won[t] = won.get(t, 0) + win
            # strength of record: a win is worth more the better the team beaten, a loss costs more the worse the team lost to
            earned[t] = earned.get(t, 0.0) + (q ** config.GOAT_CURVE if win else -(config.GOAT_LOSS + (1 - config.GOAT_LOSS) * (1 - q) ** config.GOAT_CURVE))
    lo, hi = min((earned.get(t, 0.0) for t in teams), default=0.0), max((earned.get(t, 0.0) for t in teams), default=0.0)
    beat = {t: (earned.get(t, 0.0) - lo) / (hi - lo) if hi > lo else 0.0 for t in teams}
    rec = {t: won.get(t, 0) / played[t] if played.get(t) else 0.0 for t in teams}
    size = max(in_poll.values(), default=25)        # 25 for a poll; the number of teams in a league numbered by its standings
    poll = {t: (size + 1 - in_poll[t]) / size if t in in_poll else 0.0 for t in teams}
    # strength of schedule: the average rating of the teams it has played, stretched to run from 0 for
    # the easiest schedule to 1 for the hardest (a team that has not played yet gets the easiest)
    avg = {t: sum(faced[t]) / len(faced[t]) for t in teams if faced.get(t)}
    low, high = min(avg.values(), default=0.0), max(avg.values(), default=0.0)
    sos = {t: (avg[t] - low) / (high - low) if t in avg and high > low else 0.0 for t in teams}
    wp, ws, wr = config.GOAT_WEIGHTS
    score = {t: wp * poll[t] + ws * sos[t] + wr * beat[t] for t in teams}
    # before anyone has played, every score is level: the ratings carried over from last season decide
    order = sorted(teams, key=lambda t: (-score[t], -rating.get(t, floor), t))
    base = {t: i + 1 for i, t in enumerate(order)}
    # head to head: having the better of another team counts once, however many games it is by
    net = {(a, b): 1 for (a, b), x in head_to_head(finals).items()
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
            "factors": {t: [round(beat[t], 3), round(poll[t], 3), round(rec[t], 3), round(sos[t], 3)] for t in teams}}


def contradictions(order: list, games: list[dict], among: set) -> int:
    """How many head-to-head results between teams in `among` the order gets
    the wrong way round (a team ranked below one it has the better of)."""
    place = {t: i for i, t in enumerate(order)}
    return sum(1 for (a, b), (wins, losses, _) in head_to_head(games).items()
               if a in among and b in among and a in place and b in place and wins > losses and place[a] > place[b])

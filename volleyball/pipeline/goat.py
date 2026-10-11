"""The GOAT ranking: the site's own order of every Division I team.

Five things decide it, in this order of importance:
  1. head to head: a team that has beaten another is ranked above it where
     that can be done without contradicting more results than it honors;
  2. who it beat: every win adds the quality of the team beaten, raised to
     GOAT_CURVE, and every loss takes away GOAT_LOSS plus the rest of 1 times
     how weak the team lost to was, raised to GOAT_CURVE. A team's quality is
     its place among all the teams by the ratings behind the odds, 0 for the
     weakest and 1 for the strongest; a team from outside the division counts
     as the weakest. So a win over a top team is worth far more than a win over
     a weak one, a loss to a weak team costs far more than a loss to a top
     one, and no loss is free. The totals are stretched to run from 0 (the
     lowest) to 1 (the highest);
  3. how good it is: its own rating (the one behind the odds, which follows the
     margins it wins and loses by and who they came against), stretched to run
     from 0 for the lowest-rated team to 1 for the highest;
  4. record: its share of matches won;
  5. the AVCA coaches poll: a ranked team gets credit for its place in it.
Parts 2 to 5 make a score, weighted by GOAT_WEIGHTS (who it beat, how good it
is, record, the poll). The poll credit is (26 - rank) / 25 for a ranked team and 0 otherwise.
The same formula is used on every GOAT site.

The order starts from that score. Then every pair of teams has a price for
being ranked the "wrong" way round: ranking a team above one that has beaten
it costs 1 for each win the other is ahead by, and ranking it above a team
with a higher score costs the gap divided by GOAT_HEAD_TO_HEAD. The GOAT order
is the one with the lowest total price, found by moving one team at a time to
wherever it lowers the total most, until no move helps. So a win lifts a team
over the team it beat when their scores are close, but not when the gap is
wide. Results that form a circle (A beat B, B beat C, C beat A) cannot all be
honored; it keeps as many as it can.
"""
from __future__ import annotations

from . import config


def head_to_head(games: list[dict]) -> dict:
    """{(team, opponent): [wins, losses, [dates won]]} from finished matches."""
    out = {}
    for g in sorted(games, key=lambda g: (g["date"], g["id"])):
        hs, vs = g["home"].get("sets"), g["away"].get("sets")
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


def rank(games: list[dict], rating: dict, teams: set, avca: dict) -> dict:
    """Rank `teams` (ids). `avca` is {id: poll rank} for the ranked teams.
    Returns {"order": [ids, best first], "base": {id: place by score alone},
    "score": {id: score}, "factors": {id: [who it beat, poll, record, how good it is]}}."""
    finals = [g for g in games if g["state"] == "final" and g["home"].get("sets") is not None
              and g["away"].get("sets") is not None and g["home"]["sets"] != g["away"]["sets"]]
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
            win = g[side]["sets"] > g[other]["sets"]
            played[t] = played.get(t, 0) + 1
            won[t] = won.get(t, 0) + win
            # who it beat: a win is worth more the better the team beaten, a loss costs more the worse the team lost to
            earned[t] = earned.get(t, 0.0) + (q ** config.GOAT_CURVE if win else -(config.GOAT_LOSS + (1 - config.GOAT_LOSS) * (1 - q) ** config.GOAT_CURVE))
    lo, hi = min((earned.get(t, 0.0) for t in teams), default=0.0), max((earned.get(t, 0.0) for t in teams), default=0.0)
    beat = {t: (earned.get(t, 0.0) - lo) / (hi - lo) if hi > lo else 0.0 for t in teams}
    rec = {t: won.get(t, 0) / played[t] if played.get(t) else 0.0 for t in teams}
    size = max(avca.values(), default=25)        # 25 for the college poll; the number of teams in a pro league
    poll = {t: (size + 1 - avca[t]) / size if t in avca else 0.0 for t in teams}
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
    # that could matter, near enough to stay quick with 350 teams.
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
    order = [t for t in order if t in avca] + [t for t in order if t not in avca]
    return {"order": order, "base": base, "score": score,
            "factors": {t: [round(beat[t], 3), round(poll[t], 3), round(rec[t], 3), round(power[t], 3)] for t in teams}}


def contradictions(order: list, games: list[dict], among: set) -> int:
    """How many head-to-head results between teams in `among` the order gets
    the wrong way round (a team ranked below one it has the better of)."""
    place = {t: i for i, t in enumerate(order)}
    return sum(1 for (a, b), (wins, losses, _) in head_to_head(games).items()
               if a in among and b in among and a in place and b in place and wins > losses and place[a] > place[b])

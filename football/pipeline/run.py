"""The scheduled job. It keeps these up to date and builds the pages:

  1. the season's schedule and scores, week by week
  2. the rankings (the AP Top 25, and the coaches' and playoff committee's)
  3. which teams are in FBS, and in which conference
  4. the box score of every finished game, behind the team and player stats
  5. each team's roster: positions, height, class, hometown and photos
  6. each player's career

Usage:  python -m pipeline.run <state_dir> <site_output_dir>

<state_dir> is this sport's folder on the repository's `state` branch:
  scoreboard.json   every game of the season, by week
  polls.json        every ranking seen, by the day it came out
  fbs.json          the FBS teams and their conferences
  box.json          the box score of every finished game
  rosters.json      each team's players as its roster lists them
  careers.json      each player's seasons
  ratings.json      every team's rating, this season and last (behind the odds)
  status.json       what happened on the last run
The NFL's copies of these (all but polls.json: it has no poll) are in the nfl/
folder inside it, and its pages in the nfl/ folder of the site. One run does
both leagues, college first; see config.use.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import traceback
from pathlib import Path

from . import cards, careers, config, espn, goat, odds, players, teams, web

SITE_SRC = Path(__file__).resolve().parents[1] / "site"


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}] {msg}", flush=True)


def read_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path: Path, obj, indent=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=indent, separators=None if indent else (",", ":"), allow_nan=False))


# ----------------------------------------------------------------- stages --
def update_schedule(state: Path, only: list[str] | None = None) -> dict:
    """Read the season's weeks (or, on a game-night run, only the weeks in `only`, as "kind-week")."""
    stored = read_json(state / "scoreboard.json", {})
    if only and stored.get("season") and stored.get("calendar"):
        season, calendar = stored["season"], stored["calendar"]
    else:
        season, calendar = espn.parse_calendar(web.get_json(config.SCOREBOARD))
        if not season:
            raise RuntimeError("ESPN's scoreboard did not say which season it is")
        if not calendar:
            calendar = stored.get("calendar") if stored.get("season") == season else None
            calendar = calendar or [w + ["", ""] for w in config.DEFAULT_WEEKS]
    if stored.get("season") != season:
        stored = {"season": season, "weeks": {}}
    stored["calendar"] = calendar
    keys = {f"{k}-{w}": (k, w) for k, w, *_ in calendar}
    todo = [k for k in keys if not only or k in only]
    urls = {config.WEEK.format(season=season, kind=keys[k][0], week=keys[k][1]): k for k in todo}
    failed = []
    for url, doc, err in web.get_many(list(urls)):
        key = urls[url]
        if err is not None:
            failed.append(key)                   # keep the copy already stored for that week
            continue
        stored["weeks"][key] = [g for g in (espn.parse_event(e, *keys[key]) for e in doc.get("events") or []) if g]
    if todo and len(failed) == len(todo):
        raise RuntimeError("the scoreboard could not be reached for any week")
    stored["weeks"] = {k: v for k, v in stored["weeks"].items() if k in keys}
    write_json(state / "scoreboard.json", stored)
    n = len({g["id"] for wk in stored["weeks"].values() for g in wk})
    log(f"schedule: {len(todo) - len(failed)} of {len(todo)} weeks read, {n:,} games in season {season}"
        + (f"; kept the old copy of {failed}" if failed else ""))
    return {"season": season, "weeks": len(todo), "weeks_failed": len(failed), "games": n}


def update_rankings(state: Path) -> dict:
    polls = read_json(state / "polls.json", {})
    found = espn.parse_rankings(web.get_json(config.RANKINGS))
    if config.POLL_TYPE not in found or len(found[config.POLL_TYPE]["rows"]) < config.POLL_SIZE:
        # ESPN takes the AP poll out of its feed for a while on Sunday while the new one is put in.
        # With one already stored that is not a failure: the stored poll stays until the new one shows.
        if not polls.get(config.POLL_TYPE):
            raise RuntimeError(f"the rankings did not read cleanly: {({k: len(v['rows']) for k, v in found.items()})}")
        found.pop(config.POLL_TYPE, None)
        log(f"rankings: the {config.POLL_NAME} is not in the feed just now; kept the one stored")
    new = []
    for kind, poll in found.items():
        seen = polls.setdefault(kind, {})
        if poll["date"] not in seen:
            new.append(f"{poll['name']} of {poll['date']}")
        seen[poll["date"]] = poll
        polls[kind] = dict(sorted(seen.items())[-25:])          # a season's worth
    write_json(state / "polls.json", polls)
    log("rankings: " + ", ".join(f"{v['name']} of {v['date']}" for v in found.values()) + (f"; new: {new}" if new else "; nothing new"))
    return {"found": {k: v["date"] for k, v in found.items()}, "new": new}


def update_fbs(state: Path) -> dict:
    board = read_json(state / "scoreboard.json", {})
    found = espn.parse_standings(web.get_json(config.STANDINGS.format(season=board.get("season"))))
    if len(found) < config.MIN_TEAMS:
        raise RuntimeError(f"the standings listed only {len(found)} teams; kept the list already stored")
    write_json(state / "fbs.json", found)
    log(f"standings: {len(found)} teams in {len({t['conf'] for t in found.values()})} conferences or divisions")
    return {"teams": len(found)}


def league_order(fbs: dict) -> list[str]:
    """A league with no poll: its teams from first to last by share of games won (a tie
    counts half), then wins, then points scored less points allowed."""
    def key(t):
        x = fbs[t]
        played = x.get("w", 0) + x.get("l", 0) + x.get("t", 0)
        pct = (x.get("w", 0) + 0.5 * x.get("t", 0)) / played if played else 0.0
        return (-pct, -x.get("w", 0), -(x.get("pf", 0) - x.get("pa", 0)), x["name"])
    return sorted(fbs, key=key)


def selection(state: Path, today: str | None = None) -> dict:
    """The newest AP poll joined to the schedule: the ranked teams, the FBS
    teams and every game. For the NFL, which has no poll, every team is
    "ranked", by its place in the league standings."""
    polls = read_json(state / "polls.json", {})
    board = read_json(state / "scoreboard.json", {})
    fbs = read_json(state / "fbs.json", {})
    main = polls.get(config.POLL_TYPE) or {}
    if config.POLL_TYPE and not main or not board.get("weeks") or not config.POLL_TYPE and not fbs:
        raise RuntimeError("nothing to build yet: " + ("no schedule" if not board.get("weeks") else "no rankings" if config.POLL_TYPE else "no standings"))
    games = {}
    for key in sorted(board["weeks"], key=lambda k: [int(x) for x in k.split("-")]):
        for g in board["weeks"][key]:
            games[g["id"]] = g          # a game listed in two weeks is kept once
    if not config.POLL_TYPE:
        # only games between the league's own teams (no all-star game)
        games = {i: g for i, g in games.items() if g["home"]["id"] in fbs and g["away"]["id"] in fbs}
    names = {}
    for g in games.values():
        for s in (g["away"], g["home"]):
            names[s["id"]] = s["name"]
    for t, info in fbs.items():
        names.setdefault(t, info["name"])
    if not fbs:
        # the conference list has not been read yet: a team counts as FBS once it has a fair share of games
        count = {}
        for g in games.values():
            for s in (g["away"], g["home"]):
                count[s["id"]] = count.get(s["id"], 0) + 1
        fbs = {t: {"name": names[t], "conf": "", "rec": {}} for t, n in count.items() if n >= 6}
    if config.POLL_TYPE:
        newest = main[max(main)]
        poll_date, poll_week = newest["date"], newest.get("week") or ""
        # the poll counts results through the day before it came out
        through = (dt.date.fromisoformat(poll_date) - dt.timedelta(days=1)).isoformat()
        ranked = [{"rank": r["rank"], "id": r["id"], "name": names.get(r["id"], r["name"]), "record": r.get("record"),
                   "prev": r.get("prev"), "points": r.get("points"), "votes": r.get("votes") or 0}
                  for r in newest["rows"][:config.POLL_SIZE]]
    else:
        poll_date, poll_week = None, ""
        through = max((g["date"] for g in games.values() if g["state"] == "final"), default=today or "")
        ranked = [{"rank": i + 1, "id": t, "name": names.get(t, fbs[t]["name"]), "record": fbs[t]["rec"].get("all") or "",
                   "prev": None, "points": None, "votes": 0} for i, t in enumerate(league_order(fbs))]
    rank = {t["id"]: t["rank"] for t in ranked}
    every = sorted(games.values(), key=lambda g: (g["date"], g["start"] or 0, g["id"]))
    for g in every:
        for s in (g["away"], g["home"]):
            s["rank"] = rank.get(s["id"])
    listed = [g for g in every if g["away"]["id"] in rank or g["home"]["id"] in rank]
    all_fbs = sorted(({"id": t, "name": names.get(t, info["name"]), "rank": rank.get(t)} for t, info in fbs.items()),
                     key=lambda t: (t["rank"] is None, t["rank"] or 0, t["name"]))
    others = {}
    for kind, label in config.OTHER_POLLS.items():
        seen = polls.get(kind) or {}
        if seen:
            p = seen[max(seen)]
            others[kind] = {"label": label, "name": p["name"], "date": p["date"],
                            "teams": [dict(r, name=names.get(r["id"], r["name"])) for r in p["rows"][:config.POLL_SIZE]]}
    return {"through": through, "poll_date": poll_date, "poll_week": poll_week, "polls_seen": len(main),
            "season": board["season"], "calendar": board.get("calendar") or [], "teams": ranked, "games": listed, "all_games": every,
            "fbs_teams": all_fbs, "fbs": fbs, "names": names, "others": others}


def _box_wanted(g: dict, have: dict | None, recent: str) -> bool:
    if g["state"] != "final":
        return False
    return have is None or have.get("status") != "F" or g["date"] >= recent


def update_boxes(state: Path, now: dt.datetime, live_only: bool = False) -> dict:
    """Read the box scores the stats need: every finished game not stored yet,
    the last few days' again (stats are corrected), and any game under way."""
    sel = selection(state)
    stored = read_json(state / "box.json", {})
    recent = (now.date() - dt.timedelta(days=config.BOX_REFRESH_DAYS)).isoformat()
    t = now.timestamp()

    def on_now(g):       # under way, or just over without its final box score
        return bool(g.get("start")) and t - config.LIVE_HOURS * 3600 <= g["start"] <= t and (
            g["state"] == "live" or (g["state"] == "final" and (stored.get(str(g["id"])) or {}).get("status") != "F"))

    if live_only:
        want = [g for g in sel["all_games"] if on_now(g)]
    else:
        want = [g for g in sel["all_games"] if on_now(g) or _box_wanted(g, stored.get(str(g["id"])), recent)]
    urls = {config.SUMMARY.format(game=g["id"]): g for g in want}
    failed = 0
    for url, doc, err in web.get_many(list(urls)):
        g = urls[url]
        if err is not None:
            failed += 1
            continue
        parsed = espn.parse_summary(doc)
        if parsed["team"] or parsed["players"]["home"] or parsed["players"]["away"] or str(g["id"]) not in stored:
            stored[str(g["id"])] = {"date": g["date"], **parsed}
    ids = {str(g["id"]) for g in sel["all_games"]}
    for gid in [k for k in stored if k not in ids]:
        del stored[gid]                         # another season's box scores are not used again
    write_json(state / "box.json", stored)
    finals = [g for g in sel["all_games"] if g["state"] == "final"]
    with_box = sum(1 for g in finals if (stored.get(str(g["id"])) or {}).get("team"))
    log(f"box scores: {len(want)} read ({failed} failed); {with_box} of {len(finals)} finished games have one")
    if want and failed == len(want):
        raise RuntimeError("no box score could be read")
    return {"fetched": len(want), "failed": failed, "finished": len(finals), "with_box": with_box}


def update_rosters(state: Path, now: dt.datetime) -> dict:
    """Read the rosters not read in the last week: positions, height, weight, class, hometown, and whether there is a photo."""
    sel = selection(state)
    stored = read_json(state / "rosters.json", {})
    stale = (now.date() - dt.timedelta(days=config.ROSTER_REFRESH_DAYS)).isoformat()
    want = [t["id"] for t in sel["fbs_teams"] if (stored.get(t["id"]) or {}).get("read", "") <= stale]
    urls = {config.ROSTER.format(team=t): t for t in want}
    failed = 0
    for url, doc, err in web.get_many(list(urls), tries=2):
        found = None if err is not None else espn.parse_roster(doc)
        if not found:
            failed += 1
            continue
        stored[urls[url]] = {"read": now.date().isoformat(), "players": found}
    keep = {t["id"] for t in sel["fbs_teams"]}
    stored = {k: v for k, v in stored.items() if k in keep}
    write_json(state / "rosters.json", stored)
    log(f"rosters: {len(want) - failed} read ({failed} failed); {len(stored)} of {len(keep)} teams have one")
    return {"read": len(want) - failed, "failed": failed, "teams": len(stored)}


def update_careers(state: Path, now: dt.datetime) -> dict:
    """Read some more players' careers (see pipeline/careers.py)."""
    sel = selection(state)
    boxes = read_json(state / "box.json", {})
    rated = players.compute(sel["fbs_teams"], sel["all_games"], boxes, read_json(state / "rosters.json", {}))
    latest = {}
    for g in sel["all_games"]:
        if g["state"] == "final":
            for s in (g["away"], g["home"]):
                kickoff = g.get("start") or int(dt.datetime.fromisoformat(g["date"] + "T20:00:00+00:00").timestamp())
                latest[s["id"]] = max(latest.get(s["id"], 0), kickoff)
    order = sorted(rated["players"], key=lambda p: (p["team_rank"] is None, not p["regular"], p["rank"] or 10**6))
    wanted = [(p["id"], latest.get(p["team_id"], 0)) for p in order]
    stored = read_json(state / "careers.json", {})
    res = careers.update(stored, wanted, int(now.timestamp()), log)
    write_json(state / "careers.json", stored)
    return res


def live_now(state: Path, now: dt.datetime) -> list[str]:
    """The weeks to read again on a game-night run: those with a game that
    kicked off in the last six hours, or kicks off in the next twenty minutes,
    and is not known to be over with its box score in. Empty when there is
    nothing to do."""
    try:
        sel = selection(state)
    except RuntimeError:
        return []
    boxes = read_json(state / "box.json", {})
    t = now.timestamp()
    weeks = set()
    for g in sel["all_games"]:
        if not g.get("start") or not (t - config.LIVE_HOURS * 3600 <= g["start"] <= t + 20 * 60):
            continue
        done = g["state"] == "final" and (boxes.get(str(g["id"])) or {}).get("status") == "F"
        if not done and g["state"] != "other":
            weeks.add(f"{g['week'][0]}-{g['week'][1]}")
    return sorted(weeks)


def game_files(out: Path, games: list[dict], boxes: dict, rated: dict) -> int:
    """One small file per game with a box score, for the game's page: game/<id>.json with each
    team's totals, its players by part of the box score (the last item of a row says whether
    the player has a card) and the scoring plays."""
    ids = {p["id"] for p in rated["players"]}
    (out / "game").mkdir(exist_ok=True)
    n = 0
    for g in games:
        b = boxes.get(str(g["id"]))
        if not b or not (b.get("team") or b["players"]["home"] or b["players"]["away"]):
            continue
        doc = {"id": g["id"], "status": b.get("status", ""), "team": b.get("team") or {}, "scoring": b.get("scoring") or [], "players": {}}
        for side in ("away", "home"):
            doc["players"][side] = {cat: [r + [1 if r[0] in ids else 0] for r in rows] for cat, rows in (b["players"].get(side) or {}).items()}
        write_json(out / "game" / f"{g['id']}.json", doc)
        g["box"] = 1
        n += 1
    return n


def read_words(src: Path = SITE_SRC) -> dict:
    """The site's wording from site/words.txt ("name = words" lines). Fails,
    before anything is published, if a line is broken or a name the pages use
    is missing, so a slip in the file leaves yesterday's site up."""
    words, bad = {}, []
    for n, line in enumerate((src / "words.txt").read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, text = line.partition("=")
        key = key.strip()
        if not sep or not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", key):
            bad.append(f"line {n}: {line.strip()[:60]!r}")
            continue
        words[key] = text.strip()
    used = set(re.findall(r'W\("([a-z0-9_.]+)"', (src / "app.js").read_text()))
    used |= set(re.findall(r'data-w="([a-z0-9_.]+)"', (src / "index.html").read_text()))
    missing = sorted(used - set(words))
    if bad or missing:
        raise RuntimeError("site/words.txt needs fixing; the site was not updated. "
                           + (f"Lines not in the form 'name = words': {bad}. " if bad else "")
                           + (f"Missing names (put these lines back): {missing}." if missing else ""))
    return words


def build_site(state: Path, out: Path, now: dt.datetime) -> dict:
    sel = selection(state)
    through, ranked, listed = sel["through"], sel["teams"], sel["games"]
    every, fbs_teams, fbs = sel["all_games"], sel["fbs_teams"], sel["fbs"]
    # Odds: rate every team from this season's results, starting from where each
    # finished last season, and give each coming game a chance.
    season = sel["season"]
    kept = read_json(state / "ratings.json", {})
    start = kept.get(str(season - 1))
    if start is None:
        first = odds.seed()
        start = first.get("ratings", {}) if first.get("season", season) < season else {}
    rating, pregame = odds.rate(every, start, set(fbs))
    kept = {k: v for k, v in kept.items() if int(k) >= season - 1}
    kept[str(season)] = {t: round(v, 3) for t, v in rating.items()}
    write_json(state / "ratings.json", kept)

    # The GOAT ranking of every FBS team: head to head, then strength of
    # schedule, the AP poll and record (see pipeline/goat.py).
    in_poll = {t["id"]: t["rank"] for t in ranked}
    division = set(fbs) | set(in_poll)
    ranking = goat.rank(every, rating, division, in_poll)
    place = {t: i + 1 for i, t in enumerate(ranking["order"])}
    polled = [t["id"] for t in ranked]
    for t in ranked:
        t["goat"] = place.get(t["id"])
    # The number shown beside a team everywhere: its poll rank if it has one,
    # otherwise 26 and on, in GOAT order, so no two teams share a number.
    shown, n = {}, config.POLL_SIZE
    for t in ranking["order"]:
        if t not in in_poll:
            n += 1
            shown[t] = n
    # Each ranked team's results against the other ranked teams, best opponent first.
    # Only games the poll has seen (played before it came out), so this view changes
    # when the poll does; the GOAT view below is redone on every run.
    has_poll = bool(config.POLL_TYPE)
    results = goat.head_to_head([g for g in every if g["date"] <= through]) if has_poll else {}
    for t in ranked:
        if not has_poll:
            break                               # a league table has no Beat and Lost to boxes
        t["beat"], t["lost"] = [], []
        for other in sorted(in_poll, key=in_poll.get):
            wins, losses, _ = results.get((t["id"], other), (0, 0, []))
            if wins:
                t["beat"].append([in_poll[other], sel["names"][other], wins, other])
            if losses:
                t["lost"].append([in_poll[other], sel["names"][other], losses, other])
    goat_top = [{"rank": i + 1, "id": t, "name": sel["names"].get(t, t), "poll": in_poll.get(t),
                 "factors": ranking["factors"][t]} for i, t in enumerate(ranking["order"])]
    results = goat.head_to_head(every)          # every result so far, not only the poll's
    for x in goat_top:
        won = sum(v[0] for (a, _), v in results.items() if a == x["id"])
        lost = sum(v[1] for (a, _), v in results.items() if a == x["id"])
        x["record"], x["beat"], x["lost"] = f"{won}-{lost}", [], []
        if not has_poll:
            x["record"] = (fbs.get(x["id"]) or {}).get("rec", {}).get("all") or x["record"]      # ties included
            del x["beat"], x["lost"]
            continue
        # every team it has played, best first by GOAT place; a team from outside FBS has no place and comes last
        played = sorted((b for (a, b) in results if a == x["id"]), key=lambda b: (place.get(b) is None, place.get(b) or 0, sel["names"].get(b, b)))
        for other in played:
            wins, losses, _ = results[(x["id"], other)]
            if wins:
                x["beat"].append([place.get(other), sel["names"].get(other, other), wins, other])
            if losses:
                x["lost"].append([place.get(other), sel["names"].get(other, other), losses, other])
    goat_info = {"top": goat_top, "weight": config.GOAT_HEAD_TO_HEAD, "weights": config.GOAT_WEIGHTS,
                 # among the poll's own 25 teams: results each order has the wrong way round
                 "poll_wrong": goat.contradictions(polled, every, set(polled)),
                 "goat_wrong": goat.contradictions(ranking["order"], every, set(polled))}

    for g in every:
        h, a = g["home"]["id"], g["away"]["id"]
        if g["state"] in ("upcoming", "live") and h in rating and a in rating:
            g["p"] = round(odds.chance(rating[h], rating[a], bool(g.get("neutral"))), 3)   # the home team's chance
        elif g["id"] in pregame:
            g["p0"] = round(pregame[g["id"]], 3)     # what the home team's chance was before a finished game
    words = read_words()                       # checked before anything is written
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE_SRC, out, ignore=shutil.ignore_patterns("words.txt"))
    # Give the script and stylesheet an address that changes whenever they do.
    # Otherwise a browser can pair a new page with the copy of the old script
    # it kept, and the page breaks until that copy expires.
    page = (out / "index.html").read_text()
    for name in ("app.js", "styles.css"):
        stamp = hashlib.sha256((out / name).read_bytes()).hexdigest()[:10]
        assert f'"{name}"' in page, f"index.html no longer refers to {name}"
        page = page.replace(f'"{name}"', f'"{name}?v={stamp}"')
    if config.LEAGUE != "college":
        # the league's own colour and icon for browser tabs and phone home screens
        (out / "manifest.json").write_text((out / "manifest.json").read_text().replace("GOAT Football", "GOAT Football: NFL"))
        for name in ("icon.svg", "icon-32.png", "icon-180.png", "icon-192.png", "icon-512.png"):
            shutil.copy(out / name.replace("icon", f"icon-{config.LEAGUE}", 1), out / name)
    (out / "index.html").write_text(page)
    # Players and team stats twice: against the ranked 25 only, and against all of
    # FBS. The site's "Top 25 / All FBS" switch chooses which file it reads.
    boxes = read_json(state / "box.json", {})
    rosters = read_json(state / "rosters.json", {})
    lines = {}                                  # every FBS player's games, for his card
    rated_fbs = players.compute(fbs_teams, every, boxes, rosters, lines)
    # with no poll every team is "ranked", so there is one set of players and of team stats, not two
    rated = players.compute(ranked, listed, boxes, rosters) if has_poll else rated_fbs
    for r, games in ((rated, listed), (rated_fbs, every)):
        r["through"] = max((g["date"] for g in games if g["state"] == "final"), default=None)
    with_box = game_files(out, every, boxes, rated_fbs)
    extras = cards.build(rated_fbs, lines, careers.by_player(read_json(state / "careers.json", {})), set(in_poll) if has_poll else set())
    (out / "cards").mkdir(parents=True, exist_ok=True)
    for team, doc in extras.items():
        write_json(out / "cards" / f"{team}.json", doc)
    write_json(out / "data.json", {
        "site": config.SITE_NAME, "league": config.SITE_FOLDER, "league_name": config.LEAGUE_NAME, "all_name": config.ALL_NAME,
        "pro": not has_poll, "updated": now.isoformat(timespec="seconds"), "season": season,
        "logos": {t: x["logo"] for t, x in fbs.items() if x.get("logo")} if not config.LOGO_URL else None,
        "standings": [{"id": t["id"], "name": t["name"], "rank": t["rank"], **{k: fbs[t["id"]].get(k) for k in ("conf", "group", "w", "l", "t", "pf", "pa", "seed", "rec", "place")}}
                      for t in ranked] if not has_poll else None,
        "poll": {"name": config.POLL_NAME, "through": through, "date": sel["poll_date"], "week": sel["poll_week"], "teams": ranked,
                 "polls_seen": sel["polls_seen"]},
        "polls": sel["others"], "calendar": sel["calendar"],
        "game_page": config.GAME_PAGE, "live_feed": config.WEEK, "live_seconds": config.LIVE_SECONDS,
        "logo": config.LOGO_URL, "photo": config.PHOTO_URL if config.SHOW_PHOTOS else "", "odds_tested": config.ODDS_TESTED, "goat": goat_info, "nr": shown, "words": words,
        "fbs": [[t["id"], t["name"], (fbs.get(t["id"]) or {}).get("conf") or "", (fbs.get(t["id"]) or {}).get("rec") or {}] for t in fbs_teams],
        "games": every})
    write_json(out / "players_fbs.json", rated_fbs)
    write_json(out / "teams_fbs.json", teams.compute(fbs_teams, every, boxes, rating, fbs, "conf" if has_poll else "div"))
    if has_poll:
        write_json(out / "players.json", rated)
        write_json(out / "teams.json", teams.compute(ranked, listed, boxes, rating, fbs))
    (out / ".nojekyll").write_text("")
    if has_poll:
        log(f"site: {config.POLL_NAME} of {sel['poll_date']}, {len(listed)} games of the {len(ranked)} ranked teams and {len(every)} in all "
            f"({len(fbs_teams)} FBS teams); {rated['regulars']} top-25 regulars rated, {rated_fbs['regulars']} in FBS")
    else:
        log(f"site ({config.LEAGUE_NAME}): {len(every)} games, {sum(1 for g in every if g['state'] == 'final')} played, {len(fbs_teams)} teams; "
            f"{len(rated_fbs['players'])} players, {rated_fbs['regulars']} regulars rated")
    return {"poll_date": sel["poll_date"], "games_listed": len(listed), "fbs_teams": len(fbs_teams), "games": len(every),
            "played": sum(1 for g in every if g["state"] == "final"), "game_pages": with_box,
            "players": len(rated["players"]), "regulars": rated["regulars"],
            "fbs_players": len(rated_fbs["players"]), "fbs_regulars": rated_fbs["regulars"],
            "with_odds": sum(1 for g in every if "p" in g), "with_channel": sum(1 for g in every if g.get("tv")), "teams_rated": len(rating)}


def main(state_dir: str, out_dir: str) -> int:
    state, out = Path(state_dir), Path(out_dir)
    state.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    if os.environ.get("NOW"):                           # for the tests: pretend it is this moment
        now = dt.datetime.fromisoformat(os.environ["NOW"])
    status = {"started_utc": now.isoformat(timespec="seconds"),
              "commit": os.environ.get("GITHUB_SHA", "local")[:12], "stages": {}}
    offline = os.environ.get("SKIP_FETCH") == "1"       # rebuild the pages from what is stored
    live = os.environ.get("RUN_MODE") == "live" and not offline

    def stage(name, fn):
        try:
            status["stages"][name] = {"ok": True, "result": fn()}
        except Exception as e:
            log(f"STAGE {name} FAILED: {e!r}")
            traceback.print_exc()
            status["stages"][name] = {"ok": False, "error": repr(e)}
        write_json(state / "status.json", status, indent=1)

    def folders(league):
        config.use(league)
        return (state / config.STATE_FOLDER if config.STATE_FOLDER else state), (out / config.SITE_FOLDER if config.SITE_FOLDER else out)

    def named(name):         # the NFL's stages are listed under their own names
        return name if config.LEAGUE == "college" else f"{config.LEAGUE_NAME} {name}"

    try:
        if live:
            # a game-night run: only the games under way or just finished, in either league
            on = {}
            for league in config.LEAGUES:
                st, _ = folders(league)
                on[league] = live_now(st, now)
            if not any(on.values()):
                log("game-night run: no game is on right now; nothing to do")
                return 0
        for league in config.LEAGUES:
            st, dest = folders(league)
            st.mkdir(parents=True, exist_ok=True)
            if live and on[league]:
                todo = on[league]
                stage(named("scores now"), lambda: update_schedule(st, todo))
                if not config.POLL_TYPE:
                    stage(named("standings"), lambda: update_fbs(st))     # a team's number is its place in the standings
                stage(named("box scores now"), lambda: update_boxes(st, now, live_only=True))
            elif not live and not offline:
                # a failed look at any of these leaves the stored copy in use
                stage(named("schedule"), lambda: update_schedule(st))
                if config.POLL_TYPE:
                    stage(named("rankings"), lambda: update_rankings(st))
                stage(named("conferences" if config.POLL_TYPE else "standings"), lambda: update_fbs(st))
                stage(named("box scores"), lambda: update_boxes(st, now))
                stage(named("rosters"), lambda: update_rosters(st, now))
                stage(named("careers"), lambda: update_careers(st, now))
            # the college pages are built first: they are the folder the NFL's pages go inside
            stage(named("site"), lambda: build_site(st, dest, now))
    finally:
        config.use("college")
    status["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    status["ok"] = all(s["ok"] for s in status["stages"].values())
    write_json(state / "status.json", status, indent=1)
    log(("game-night run" if live else "run") + " finished: " + ("OK" if status["ok"] else "WITH ERRORS"))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

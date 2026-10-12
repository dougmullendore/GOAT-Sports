"""The scheduled job. It keeps these up to date and builds the pages:

  1. the season's schedule and scores, day by day
  2. the rankings (the AP Top 25 and the coaches poll)
  3. which teams are in the league, and in which conference or division
  4. the box score of every finished game, behind the team and player stats
  5. each team's roster: positions, height, class, hometown and photos
  6. each player's career

Usage:  python -m pipeline.run <state_dir> <site_output_dir>

<state_dir> is this sport's folder on the repository's `state` branch:
  scoreboard.json   every game of the season, by day
  polls.json        every ranking seen, by the day it came out
  fbs.json          the league's teams and their conferences
  box.json          the box score of every finished game
  rosters.json      each team's players as its roster lists them
  careers.json      each player's seasons
  ratings.json      every team's rating, this season and last (behind the odds)
  status.json       what happened on the last run
The second league's copies of these (all but polls.json: it has no poll) are in
its own folder inside it, and its pages in the same folder of the site. One run
does every league in config.LEAGUES, the first one first; see config.use.
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

from . import backup, cards, careers, config, espn, goat, odds, players, power, social, teams, web

SITE_SRC = Path(__file__).resolve().parents[1] / "site"


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}] {msg}", flush=True)


def read_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path: Path, obj, indent=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=indent, separators=None if indent else (",", ":"), allow_nan=False))


def each_day(first: str, last: str) -> list[str]:
    d, end, out = dt.date.fromisoformat(first), dt.date.fromisoformat(last), []
    while d <= end:
        out.append(d.strftime("%Y%m%d"))
        d += dt.timedelta(days=1)
    return out


def day_is_due(day: str, read: str | None, today: dt.date) -> bool:
    """Whether a full run should read this day of the schedule (again)."""
    if not read:
        return True
    d = dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))
    if d < today - dt.timedelta(days=config.DAYS_BACK):
        return False                                   # played and settled
    if d <= today + dt.timedelta(days=config.DAYS_AHEAD):
        return True
    return (today - dt.date.fromisoformat(read)).days >= config.FAR_REFRESH_DAYS


# ----------------------------------------------------------------- stages --
def from_backup(games: list[dict], now: dt.datetime, nothing_read: bool, what: str) -> int:
    """The usual scoreboard could not be read for these games: bring those under way
    or just over up to date from the backup scoreboard. With nothing read from either,
    the stage fails and the stored copy stays in use."""
    try:
        got = backup.patch(games, now, config.BACKUP, log)
    except Exception as e:
        if nothing_read:
            raise RuntimeError(f"the scoreboard could not be reached for any {what}") from e
        log(f"backup scoreboard: not used: {e!r}"[:200])
        return 0
    for g in games:
        g.pop("backup", None)
    if nothing_read and not got["days"]:
        raise RuntimeError(f"the scoreboard could not be reached for any {what}")
    return got["changed"]


NEXT_SEASON = "scoreboard_next.json"       # the coming season's schedule, kept aside while last season is still shown


def season_started(store: dict, today: dt.date) -> bool:
    """Whether a game that counts (not a warm-up) has reached its day."""
    kinds = (1, 2, 3) if config.PRESEASON_GAMES else (2, 3)        # the NBA's season begins with its warm-up games
    return any(g.get("kind") in kinds and g.get("date") and g["date"] <= today.isoformat()
               for d in (store.get("days") or {}).values() for g in d["games"])


def read_days(store: dict, season: int, first: str, last: str, today: dt.date) -> tuple[dict, list[str], list[str]]:
    """Bring one season's stored schedule up to date: (the schedule, the days that were due, those that could not be read)."""
    if store.get("season") != season or store.get("preseason", False) != config.PRESEASON_GAMES:
        store = {"season": season, "days": {}}       # (a change in whether warm-up games are listed: every day is read again)
    store["preseason"] = config.PRESEASON_GAMES
    store["first"], store["last"] = first, last
    days = each_day(first, last)
    store["days"] = {d: v for d, v in store["days"].items() if d in set(days)}
    todo = [d for d in days if day_is_due(d, (store["days"].get(d) or {}).get("read"), today)]
    urls = {config.DAY.format(day=d): d for d in todo}
    failed = []
    for url, doc, err in web.get_many(list(urls)):
        day = urls[url]
        if err is not None:
            failed.append(day)                   # keep the copy already stored for that day
            continue
        store["days"][day] = {"read": today.isoformat(), "games": [g for g in (espn.parse_event(e, day) for e in doc.get("events") or []) if g]}
    return store, todo, failed


def update_schedule(state: Path, now: dt.datetime, only: list[str] | None = None) -> dict:
    """Read the days of the season that are due (or, on a game-night run, only the days in `only`).

    Until a new season's first game that counts reaches its day, the site goes on showing last
    season: scoreboard.json holds last season, read once, and the coming season's schedule is
    kept in scoreboard_next.json so its games can be listed as still to come. On the day the
    new season begins it takes over scoreboard.json, and everything else follows it."""
    stored = read_json(state / "scoreboard.json", {})
    today = now.date()
    coming = None                    # the coming season's schedule, while last season is shown
    if only and stored.get("season") and stored.get("days"):
        season, todo, failed = stored["season"], list(only), []
        urls = {config.DAY.format(day=d): d for d in todo}
        for url, doc, err in web.get_many(list(urls)):
            day = urls[url]
            if err is not None:
                failed.append(day)
                continue
            stored["days"][day] = {"read": today.isoformat(), "games": [g for g in (espn.parse_event(e, day) for e in doc.get("events") or []) if g]}
    else:
        try:
            season, first, last = espn.parse_season(web.get_json(config.SCOREBOARD))
            if not season or not first or not last:
                raise RuntimeError("ESPN's scoreboard did not say which season it is, or when it runs")
        except Exception as e:
            if not (stored.get("season") and stored.get("first") and stored.get("last") and stored.get("days")):
                raise
            log(f"schedule: the season's dates could not be read ({e!r}); using the stored ones"[:200])
            season, first, last = stored["season"], stored["first"], stored["last"]
        kept = read_json(state / NEXT_SEASON, {})
        if stored.get("season") == season and not season_started(stored, today):
            kept, stored = stored, {}            # this season has not begun: its schedule goes aside
        if stored.get("season") != season:       # last season is on show (or nothing is yet)
            kept, todo, failed = read_days(kept if kept.get("season") == season else {}, season, first, last, today)
            if season_started(kept, today):
                stored = kept                    # the new season begins today: it takes over
            else:
                coming = kept
        fresh = stored is kept                   # a season that has just taken over was read a moment ago
        if coming is not None:
            before = season - 1
            try:
                if stored.get("season") != before or not stored.get("first"):
                    found, first, last = espn.parse_season(web.get_json(config.DAY.format(day=config.LAST_SEASON_DAY.format(year=before))))
                    if found != before or not first or not last:
                        raise RuntimeError(f"ESPN's scoreboard did not give the dates of the {before} season")
                else:
                    first, last = stored["first"], stored["last"]
                old, old_todo, old_failed = read_days(stored, before, first, last, today)
                if not any(d["games"] for d in old["days"].values()):
                    raise RuntimeError("none of last season's days could be read")
                write_json(state / NEXT_SEASON, coming)
                stored, todo, failed, season = old, old_todo, old_failed, before
            except Exception as e:
                # last season cannot be shown just now: show the coming season, as before any game is played
                log(f"schedule: last season could not be read ({e!r}); showing the coming season for now"[:220])
                stored, coming, fresh = coming, None, True
        if coming is None:
            if (state / NEXT_SEASON).exists():
                (state / NEXT_SEASON).unlink()
            if not fresh:
                stored, todo, failed = read_days(stored, season, first, last, today)
    patched = 0
    if failed:
        patched = from_backup([g for d in failed for g in (stored["days"].get(d) or {}).get("games") or []], now,
                              len(failed) == len(todo), "day")
    write_json(state / "scoreboard.json", stored)
    n = len({g["id"] for d in stored["days"].values() for g in d["games"]})
    log(f"schedule: {len(todo) - len(failed)} of {len(todo)} days read, {n:,} games in season {season}"
        + (f"; kept the old copy of {len(failed)} days" if failed else "")
        + (f"; last season is shown until the {coming['season']} season begins" if coming is not None else ""))
    return {"season": season, "days": len(todo), "days_failed": len(failed), "games": n, "from_backup": patched,
            "showing_last_season": coming is not None}


def update_rankings(state: Path) -> dict:
    """Keep the rankings that belong to this season. Before the preseason poll comes out the
    feed still carries last season's final one, which is left alone."""
    polls = read_json(state / "polls.json", {})
    season = read_json(state / "scoreboard.json", {}).get("season")
    if polls.get("season") != season:
        polls = {"season": season}
    found = {k: v for k, v in espn.parse_rankings(web.get_json(config.RANKINGS)).items() if v.get("season") in (None, season)}
    new = []
    for kind, poll in found.items():
        seen = polls.setdefault(kind, {})
        if poll["date"] not in seen:
            new.append(f"{poll['name']} of {poll['date']}")
        seen[poll["date"]] = poll
        polls[kind] = dict(sorted(seen.items())[-30:])          # a season's worth
    write_json(state / "polls.json", polls)
    if not found:
        log(f"rankings: none yet for the {season} season")
    else:
        log("rankings: " + ", ".join(f"{v['name']} of {v['date']}" for v in found.values()) + (f"; new: {new}" if new else "; nothing new"))
    return {"found": {k: v["date"] for k, v in found.items()}, "new": new}


def update_fbs(state: Path) -> dict:
    """The league's teams, with their conferences and records. Before a season's first games the
    standings can be empty: then last season's list of teams is used, with no records."""
    season = read_json(state / "scoreboard.json", {}).get("season")
    found = espn.parse_standings(web.get_json(config.STANDINGS.format(season=season)))
    carried = False
    if len(found) < config.MIN_TEAMS and season:
        before = espn.parse_standings(web.get_json(config.STANDINGS.format(season=season - 1)))
        if len(before) >= config.MIN_TEAMS:
            for t in before.values():
                t.update(w=0, l=0, t=0, pf=0, pa=0, seed=0, gb="", rec={})
            found, carried = before, True
    if len(found) < config.MIN_TEAMS:
        raise RuntimeError(f"the standings listed only {len(found)} teams; kept the list already stored")
    write_json(state / "fbs.json", found)
    log(f"standings: {len(found)} teams in {len({t['conf'] for t in found.values()})} conferences or divisions"
        + (" (last season's list: this season's standings are still empty)" if carried else ""))
    return {"teams": len(found), "from_last_season": carried}


def power_teams(state: Path) -> dict:
    """{team: [ESPN's short name, full name, nickname, name]} for matching ESPN's power rankings to the league's teams."""
    return {t: [v.get("abbr") or "", f"{v.get('place') or ''} {v.get('nick') or ''}".strip(), v.get("nick"), v.get("name")]
            for t, v in read_json(state / "fbs.json", {}).items()}


def frozen_credit(state: Path, season, over: bool, credit: dict, now: dt.datetime) -> tuple[dict, str | None]:
    """The GOAT ranking stops changing when the regular season ends. Its games and ratings are the
    regular season's anyway; this keeps the poll (or power ranking, or standings) it is built on as
    it stood when the first postseason game began. Returns (the credit to use, when it was frozen)."""
    path = state / "goat_frozen.json"
    kept = read_json(path, {})
    if not over:
        return credit, None
    if kept.get("season") == season and kept.get("credit"):
        return kept["credit"], kept.get("frozen")
    write_json(path, {"season": season, "frozen": now.date().isoformat(), "credit": credit})
    return credit, now.date().isoformat()


def league_order(fbs: dict) -> list[str]:
    """A league with no poll: its teams from first to last by share of games won, then
    wins, then points scored less points allowed."""
    def key(t):
        x = fbs[t]
        played = x.get("w", 0) + x.get("l", 0)
        return (-(x.get("w", 0) / played if played else 0.0), -x.get("w", 0), -(x.get("pf", 0) - x.get("pa", 0)), x["name"])
    return sorted(fbs, key=key)


def selection(state: Path) -> dict:
    """The newest AP poll joined to the schedule: the ranked teams, every team of
    the league and every game. For the NBA, which has no poll, every team is
    "ranked", by its place in the league standings. Before a college season's
    first poll there are no ranked teams at all."""
    polls = read_json(state / "polls.json", {})
    board = read_json(state / "scoreboard.json", {})
    fbs = read_json(state / "fbs.json", {})
    main = polls.get(config.POLL_TYPE) or {} if config.POLL_TYPE else {}
    if not board.get("days"):
        raise RuntimeError("nothing to build yet: no schedule")
    if not config.POLL_TYPE and not fbs:
        raise RuntimeError("nothing to build yet: no standings")
    games = {}
    for day in sorted(board["days"], key=lambda d: (board["days"][d].get("read") or "", d)):
        for g in board["days"][day]["games"]:
            games[g["id"]] = g          # a game moved to another day is kept once, from the day read last
    # While last season is on show, the coming season's games are listed too, as still to come.
    coming = read_json(state / NEXT_SEASON, {})
    last_season = coming.get("season") == board["season"] + 1
    next_first = None
    if last_season:
        for day in coming.get("days") or {}:
            for g in coming["days"][day]["games"]:
                if g["id"] not in games and g["state"] != "final":
                    games[g["id"]] = dict(g, next=1)
                    next_first = min(next_first or g["date"], g["date"])
    # warm-up games are listed but never counted
    preseason = sorted((g for g in games.values() if g.get("kind") == 1), key=lambda g: (g["date"], g["start"] or 0, g["id"]))
    games = {i: g for i, g in games.items() if g.get("kind") != 1}
    if not config.POLL_TYPE:
        preseason = [g for g in preseason if g["home"]["id"] in fbs and g["away"]["id"] in fbs]
        # only games between the league's own teams (no all-star game)
        games = {i: g for i, g in games.items() if g["home"]["id"] in fbs and g["away"]["id"] in fbs}
    names = {}
    for g in games.values():
        for s in (g["away"], g["home"]):
            names[s["id"]] = s["name"]
    for t, info in fbs.items():
        names.setdefault(t, info["name"])
    if not fbs:
        # the list of teams has not been read yet: a team counts once it has a fair share of games
        count = {}
        for g in games.values():
            for s in (g["away"], g["home"]):
                count[s["id"]] = count.get(s["id"], 0) + 1
        fbs = {t: {"name": names[t], "conf": "", "rec": {}} for t, n in count.items() if n >= 10}
    finals = [g["date"] for g in games.values() if g["state"] == "final"]
    numbered = True                 # whether the numbers beside teams mean anything yet
    if config.POLL_TYPE and main:
        newest = main[max(main)]
        poll_date, poll_week = newest["date"], newest.get("week") or ""
        # the poll counts results through the day before it came out
        through = (dt.date.fromisoformat(poll_date) - dt.timedelta(days=1)).isoformat()
        ranked = [{"rank": r["rank"], "id": r["id"], "name": names.get(r["id"], r["name"]), "record": r.get("record"),
                   "prev": r.get("prev"), "points": r.get("points"), "votes": r.get("votes") or 0}
                  for r in newest["rows"][:config.POLL_SIZE]]
    elif config.POLL_TYPE:
        poll_date, poll_week, through, ranked, numbered = None, "", max(finals, default=""), [], False
    else:
        if not finals:
            # before the first game that counts, the feed's standings are the warm-up games': start everyone level
            fbs = {t: dict(x, w=0, l=0, t=0, pf=0, pa=0, seed=None, gb="", rec={}) for t, x in fbs.items()}
        poll_date, poll_week, through = None, "", max(finals, default="")
        ranked = [{"rank": i + 1, "id": t, "name": names.get(t, fbs[t]["name"]), "record": (fbs[t].get("rec") or {}).get("all") or "",
                   "prev": None, "points": None, "votes": 0} for i, t in enumerate(league_order(fbs))]
        numbered = any(x.get("w", 0) + x.get("l", 0) for x in fbs.values())
    rank = {t["id"]: t["rank"] for t in ranked}
    every = sorted(games.values(), key=lambda g: (g["date"], g["start"] or 0, g["id"]))
    for g in every + preseason:
        for s in (g["away"], g["home"]):
            s["rank"] = rank.get(s["id"])
    listed = [g for g in every if g["away"]["id"] in rank or g["home"]["id"] in rank]
    all_fbs = sorted(({"id": t, "name": names.get(t, info["name"]), "rank": rank.get(t)} for t, info in fbs.items()),
                     key=lambda t: (t["rank"] is None, t["rank"] or 0, t["name"]))
    others = {}
    for kind, label in config.OTHER_POLLS.items():
        seen = polls.get(kind) or {}
        if seen and main:
            p = seen[max(seen)]
            others[kind] = {"label": label, "name": p["name"], "date": p["date"],
                            "teams": [dict(r, name=names.get(r["id"], r["name"])) for r in p["rows"][:config.POLL_SIZE]]}
    return {"through": through, "poll_date": poll_date, "poll_week": poll_week, "polls_seen": len(main), "numbered": numbered,
            "season": board["season"], "first": board.get("first"), "last": (coming.get("last") if last_season else None) or board.get("last"),
            "last_season": last_season, "next_first": next_first, "preseason": preseason, "teams": ranked, "games": listed,
            "all_games": every, "fbs_teams": all_fbs, "fbs": fbs, "names": names, "others": others}


def update_boxes(state: Path, now: dt.datetime, live_only: bool = False) -> dict:
    """Read the box scores the stats need: every finished game not stored yet,
    the last couple of days' again (stats are corrected), and any game under
    way. At most BOXES_PER_RUN a run, newest first."""
    sel = selection(state)
    stored = read_json(state / "box.json", {})
    recent = (now.date() - dt.timedelta(days=config.BOX_REFRESH_DAYS)).isoformat()
    t = now.timestamp()
    listed = {g["id"] for g in sel["all_games"]}
    fbs = set(sel["fbs"])

    def on_now(g):       # under way, or just over without its final box score
        return bool(g.get("start")) and t - config.LIVE_HOURS * 3600 <= g["start"] <= t and (
            g["state"] == "live" or (g["state"] == "final" and (stored.get(str(g["id"])) or {}).get("status") != "F"))

    def wanted(g):
        have = stored.get(str(g["id"]))
        return g["state"] == "final" and (have is None or have.get("status") != "F" or g["date"] >= recent)

    want = [g for g in sel["all_games"] if on_now(g) or (not live_only and wanted(g))]
    want.sort(key=lambda g: (g["date"], g["start"] or 0), reverse=True)
    left = max(0, len(want) - config.BOXES_PER_RUN)
    want = want[:config.BOXES_PER_RUN]
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
    for gid in [k for k in stored if int(k) not in listed]:
        del stored[gid]                         # another season's box scores are not used again
    write_json(state / "box.json", stored)
    finals = [g for g in sel["all_games"] if g["state"] == "final" and (g["home"]["id"] in fbs or g["away"]["id"] in fbs)]
    with_box = sum(1 for g in finals if (stored.get(str(g["id"])) or {}).get("team"))
    log(f"box scores: {len(want)} read ({failed} failed); {with_box} of {len(finals)} finished games have one"
        + (f"; {left} more to read on later runs" if left else ""))
    if want and failed == len(want):
        raise RuntimeError("no box score could be read")
    return {"fetched": len(want), "failed": failed, "finished": len(finals), "with_box": with_box, "to_read": left}


def update_rosters(state: Path, now: dt.datetime) -> dict:
    """Read the rosters not read in the last week: positions, height, weight, class, hometown, and whether there is a photo."""
    sel = selection(state)
    stored = read_json(state / "rosters.json", {})
    stale = (now.date() - dt.timedelta(days=config.ROSTER_REFRESH_DAYS)).isoformat()
    # ranked teams first, so a first run that cannot read them all starts with the ones most looked at
    want = [t["id"] for t in sel["fbs_teams"] if (stored.get(t["id"]) or {}).get("read", "") <= stale][:config.ROSTERS_PER_RUN]
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
            kickoff = g.get("start") or int(dt.datetime.fromisoformat(g["date"] + "T23:00:00+00:00").timestamp())
            for s in (g["away"], g["home"]):
                latest[s["id"]] = max(latest.get(s["id"], 0), kickoff)
    order = sorted(rated["players"], key=lambda p: (p["team_rank"] is None, not p["regular"], p["rank"] or 10**6))
    wanted = [(p["id"], latest.get(p["team_id"], 0)) for p in order]
    stored = read_json(state / "careers.json", {})
    res = careers.update(stored, wanted, int(now.timestamp()), log)
    write_json(state / "careers.json", stored)
    return res


def live_now(state: Path, now: dt.datetime) -> list[str]:
    """The days to read again on a game-night run: those with a game that
    tipped off in the last few hours, or tips off in the next twenty minutes,
    and is not known to be over with its box score in. Empty when there is
    nothing to do."""
    try:
        sel = selection(state)
    except RuntimeError:
        return []
    boxes = read_json(state / "box.json", {})
    t = now.timestamp()
    days = set()
    for g in sel["all_games"]:
        if not g.get("start") or not (t - config.LIVE_HOURS * 3600 <= g["start"] <= t + 20 * 60):
            continue
        done = g["state"] == "final" and (boxes.get(str(g["id"])) or {}).get("status") == "F"
        if not done and g["state"] != "other":
            days.add(g["day"])
    return sorted(days)


def game_files(out: Path, games: list[dict], boxes: dict, rated: dict) -> int:
    """One small file per game with a box score, for the game's page: game/<id>.json with each
    team's totals and its players (the last item of a row says whether the player has a card)."""
    ids = {p["id"] for p in rated["players"]}
    (out / "game").mkdir(exist_ok=True)
    n = 0
    for g in games:
        b = boxes.get(str(g["id"]))
        if not b or not (b.get("team") or b["players"]["home"] or b["players"]["away"]):
            continue
        doc = {"id": g["id"], "status": b.get("status", ""), "team": b.get("team") or {}, "players": {}}
        for side in ("away", "home"):
            doc["players"][side] = [r + [1 if r[0] in ids else 0] for r in b["players"].get(side) or []]
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


def season_label(season: int) -> str:
    """A season that runs over the new year is named by both ("2026-27")."""
    return f"{season - 1}-{str(season)[2:]}" if config.SEASON_SPANS_YEARS else str(season)


def build_site(state: Path, out: Path, now: dt.datetime) -> dict:
    sel = selection(state)
    through, ranked, listed = sel["through"], sel["teams"], sel["games"]
    every, fbs_teams, fbs = sel["all_games"], sel["fbs_teams"], sel["fbs"]
    has_poll_type = bool(config.POLL_TYPE)          # a college league; False for a pro league, numbered by its standings
    has_poll = has_poll_type and bool(ranked)       # and its poll is out
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

    # The GOAT ranking of every team: head to head, then who it
    # beat, record and the poll (or the standings) (see pipeline/goat.py).
    in_poll = {t["id"]: t["rank"] for t in ranked}
    division = set(fbs) | set(in_poll)
    # before a league table means anything, the order is the ratings carried over from last season
    # a pro league has no poll: ESPN's newest power ranking stands in for one, and the standings for that
    # (not while last season is on show: ESPN's newest ranking is about the season to come)
    espn_power = power.stored(state, division) if not config.POLL_TYPE and not sel["last_season"] else {}
    # Regular season only, and frozen once the postseason starts: the games, the ratings and the poll
    # it is built on all stop where the regular season did.
    regular = [g for g in every if not (g.get("kind") == 3)]
    over = any((g.get("kind") == 3) and g["state"] in ("live", "final") for g in every)
    credit, frozen = frozen_credit(state, season, over, espn_power.get("ranks") or (in_poll if sel["numbered"] else {}), now)
    goat_rating = odds.rate(regular, start, set(fbs))[0] if over else rating
    ranking = goat.rank(regular, goat_rating, division, credit)
    place = {t: i + 1 for i, t in enumerate(ranking["order"])}
    polled = [t["id"] for t in ranked]
    for t in ranked:
        t["goat"] = place.get(t["id"])
    # The number shown beside a team everywhere: its poll rank if it has one,
    # otherwise 26 and on, in GOAT order, so no two teams share a number.
    shown, n = {}, config.POLL_SIZE
    for t in ranking["order"]:
        if has_poll and t not in in_poll:
            n += 1
            shown[t] = n
    # Each ranked team's results against the other ranked teams, best opponent first.
    # Only games the poll has seen (played before it came out), so this view changes
    # when the poll does; the GOAT view below is redone on every run.
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
    for x in goat_top:
        if espn_power:
            x["power"] = (credit if frozen else espn_power["ranks"]).get(x["id"])     # once frozen, the ranking it was frozen with
    in_goat = {x["id"]: x["rank"] for x in goat_top[:config.POLL_SIZE]}
    results = goat.head_to_head(regular)        # every regular-season result so far, not only the poll's
    for x in goat_top:
        won = sum(v[0] for (a, _), v in results.items() if a == x["id"])
        lost = sum(v[1] for (a, _), v in results.items() if a == x["id"])
        x["record"] = f"{won}-{lost}"
        if not has_poll_type:
            continue
        x["beat"], x["lost"] = [], []
        for other in sorted(in_goat, key=in_goat.get):
            wins, losses, _ = results.get((x["id"], other), (0, 0, []))
            if wins:
                x["beat"].append([in_goat[other], sel["names"][other], wins, other])
            if losses:
                x["lost"].append([in_goat[other], sel["names"][other], losses, other])
    goat_info = {"top": goat_top, "weight": config.GOAT_HEAD_TO_HEAD, "weights": config.GOAT_WEIGHTS, "frozen": frozen,
                 "power": {k: espn_power.get(k) for k in ("headline", "published", "url")} if espn_power else None,
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
    if config.LEAGUE != config.LEAGUES[0]:
        # the league's own colour and icon for browser tabs and phone home screens
        page = page.replace(f'content="{config.COLOURS[0]}"', f'content="{config.COLOURS[1]}"')
        (out / "manifest.json").write_text((out / "manifest.json").read_text().replace(config.COLOURS[0], config.COLOURS[1])
                                           .replace(config.SITE_NAME, f"{config.SITE_NAME}: {config.LEAGUE_NAME}"))
    (out / "index.html").write_text(page)
    # Players and team stats twice: against the ranked 25 only, and against the whole
    # league. The site's "Top 25 / All" switch chooses which file it reads.
    boxes = read_json(state / "box.json", {})
    rosters = read_json(state / "rosters.json", {})
    lines = {}                                  # every player's games, for his card
    rated_fbs = players.compute(fbs_teams, every, boxes, rosters, lines)
    # with no poll there is one set of players and of team stats, not two
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
        "leagues": config.LEAGUE_TABS, "pro": not has_poll_type, "no_poll": has_poll_type and not has_poll, "numbered": sel["numbered"],
        "updated": now.isoformat(timespec="seconds"), "season": season, "season_label": season_label(season),
        # set while a new season has not begun and last season's numbers are still on show
        "last_season": {"next": season_label(season + 1), "starts": sel["next_first"]} if sel["last_season"] else None,
        "first": sel["first"], "last": sel["last"], "periods": config.PERIODS,
        "logos": {t: x["logo"] for t, x in fbs.items() if x.get("logo")} if not config.LOGO_URL else None,
        "standings": [{"id": t["id"], "name": t["name"], "rank": t["rank"], **{k: fbs[t["id"]].get(k) for k in ("conf", "group", "w", "l", "t", "pf", "pa", "seed", "gb", "rec", "place")}}
                      for t in ranked] if not has_poll_type else None,
        "poll": {"name": config.POLL_NAME, "through": through, "date": sel["poll_date"], "week": sel["poll_week"], "teams": ranked,
                 "polls_seen": sel["polls_seen"]},
        "polls": sel["others"],
        "game_page": config.GAME_PAGE, "live_feed": config.DAY, "live_seconds": config.LIVE_SECONDS,
        "logo": config.LOGO_URL, "photo": config.PHOTO_URL if config.SHOW_PHOTOS else "", "odds_tested": config.ODDS_TESTED,
        "goat": goat_info, "nr": shown, "words": words,
        "fbs": [[t["id"], t["name"], (fbs.get(t["id"]) or {}).get("conf") or "", (fbs.get(t["id"]) or {}).get("rec") or {}] for t in fbs_teams],
        "games": sorted(every + [dict(g, round="Preseason") for g in sel["preseason"]], key=lambda g: (g["date"], g["start"] or 0, g["id"]))})
    for r in (rated, rated_fbs):
        social.add(state, r["players"])          # links to a player's own pages, where they are known
    write_json(out / "players_fbs.json", rated_fbs)
    write_json(out / "teams_fbs.json", teams.compute(fbs_teams, every, boxes, rating, fbs, "conf" if has_poll_type else "div"))
    if has_poll:
        write_json(out / "players.json", rated)
        write_json(out / "teams.json", teams.compute(ranked, listed, boxes, rating, fbs))
    (out / ".nojekyll").write_text("")
    played = sum(1 for g in every if g["state"] == "final")
    log(f"site ({config.LEAGUE_NAME}): " + (f"{config.POLL_NAME} of {sel['poll_date']}, " if has_poll else "no poll yet, " if has_poll_type else "")
        + f"{len(every):,} games, {played:,} played, {len(fbs_teams)} teams; {len(rated_fbs['players']):,} players, {rated_fbs['regulars']:,} regulars rated")
    return {"poll_date": sel["poll_date"], "games_listed": len(listed), "teams": len(fbs_teams), "games": len(every),
            "played": played, "game_pages": with_box, "players": len(rated_fbs["players"]), "regulars": rated_fbs["regulars"],
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

    def named(name):         # every league's stages are listed under its own name
        return f"{config.LEAGUE_NAME} {name}"

    try:
        if live:
            # a game-night run: only the games under way or just finished, in any league
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
                stage(named("scores now"), lambda: update_schedule(st, now, todo))
                if not config.POLL_TYPE:
                    stage(named("standings"), lambda: update_fbs(st))     # a team's number is its place in the standings
                stage(named("box scores now"), lambda: update_boxes(st, now, live_only=True))
            elif not live and not offline:
                # a failed look at any of these leaves the stored copy in use
                stage(named("schedule"), lambda: update_schedule(st, now))
                if config.POLL_TYPE:
                    stage(named("rankings"), lambda: update_rankings(st))
                stage(named("standings"), lambda: update_fbs(st))
                stage(named("box scores"), lambda: update_boxes(st, now))
                stage(named("rosters"), lambda: update_rosters(st, now))
                stage(named("careers"), lambda: update_careers(st, now))
                stage(named("social links"), lambda: social.update(st, now.date(), log))
                if not config.POLL_TYPE:       # a pro league: ESPN's newest power ranking, in place of a poll
                    stage(named("power ranking"), lambda: power.update(st, now, power_teams(st), log))
            # the first league's pages are built first: they are the folder the others' pages go inside
            stage(named("site"), lambda: build_site(st, dest, now))
    finally:
        config.use(config.LEAGUES[0])
    status["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    status["ok"] = all(s["ok"] for s in status["stages"].values())
    write_json(state / "status.json", status, indent=1)
    log(("game-night run" if live else "run") + " finished: " + ("OK" if status["ok"] else "WITH ERRORS"))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

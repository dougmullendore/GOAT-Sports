"""A second place to read scores, for when the usual feed cannot be read.

Yahoo's public scoreboard gives every game of a day with its score and
whether it is over. It is only ever used to bring games the site already
lists up to date: nothing is added from it, a finished game is never changed,
and a game is only touched when both of its teams are found in Yahoo's game
at the same time of day. Box scores still come from the usual feed, so they
fill in once it is back.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from . import web

URL = "https://api-secure.sports.yahoo.com/v1/editorial/s/scoreboard?leagues={league}&date={date}"
_EAST = ZoneInfo("America/New_York")
BEFORE, AFTER = 30 * 3600, 3600        # games that started up to 30 hours ago, or start within the hour
MAX_DAYS = 3
SAME_GAME = 3 * 3600                   # both teams the same: starts this close together
ONE_TEAM = 20 * 60                     # one team the same: starts this close together


def _key(text) -> str:
    text = re.sub(r"\bsaint\b|\bst\.", "st", str(text or "").lower()).replace("&", "and")
    text = re.sub(r"\bstate\b", "st", text)
    return re.sub(r"[^a-z0-9]", "", text)


def _score(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse(doc: dict) -> list[dict]:
    """A day of Yahoo's scoreboard as [{"t": start, "state": "final" | "live" | None,
    "detail": ..., "away": {"names": {...}, "score": n}, "home": {...}}]."""
    board = ((doc or {}).get("service") or {}).get("scoreboard") or {}
    teams, out = board.get("teams") or {}, []

    def side(team_id, score):
        t = teams.get(team_id) or {}
        names = {_key(t.get(k)) for k in ("first_name", "last_name", "full_name", "display_name", "abbr")} - {""}
        return {"names": names, "score": _score(score)}

    for g in (board.get("games") or {}).values():
        try:
            t = parsedate_to_datetime(g.get("start_time") or "").timestamp()
        except (TypeError, ValueError):
            continue
        kind = str(g.get("status_type") or "")
        state = "final" if kind.endswith(".final") else "live" if "in_progress" in kind else None
        shootout = g.get("total_away_shootout_points") is not None or g.get("total_home_shootout_points") is not None
        out.append({"t": t, "state": state, "detail": g.get("status_display_name") or "",
                    "periods": _score(g.get("current_period_id")) or 0, "shootout": shootout,
                    "away": side(g.get("away_team_id"), g.get("total_away_points")),
                    "home": side(g.get("home_team_id"), g.get("total_home_points"))})
    return out


def _is(team: dict, side: dict) -> bool:
    return bool({_key(team.get("name")), _key(team.get("abbr") or team.get("id"))} - {""} & side["names"])


def find(game: dict, listed: list[dict]):
    """(Yahoo's game, whether it has the teams the other way round) for one of
    the site's games, or (None, False)."""
    best = None
    for y in listed:
        if y.get("used"):
            continue
        gap = abs(y["t"] - game["start"])
        for flip in (False, True):
            a, h = (y["home"], y["away"]) if flip else (y["away"], y["home"])
            n = _is(game["away"], a) + _is(game["home"], h)
            if (n == 2 and gap <= SAME_GAME) or (n == 1 and gap <= ONE_TEAM):
                if best is None or (-n, gap) < best[0]:
                    best = ((-n, gap), y, flip)
    return (best[1], best[2]) if best else (None, False)


def patch(games: list[dict], now: dt.datetime, league: str, log=print) -> dict:
    """Bring the games that should be under way or just over up to date from
    Yahoo. `games` are changed in place. Returns {"days": days read, "changed": n};
    raises if Yahoo could not be read either."""
    t = now.timestamp()
    due = [g for g in games if g.get("state") in ("upcoming", "live") and g.get("start") and t - BEFORE <= g["start"] <= t + AFTER]
    if not due:
        return {"days": 0, "changed": 0}
    days = sorted({dt.datetime.fromtimestamp(g["start"], _EAST).date().isoformat() for g in due})[-MAX_DAYS:]
    listed, read = [], 0
    for day in days:
        try:
            listed += parse(json.loads(web.get_bytes(URL.format(league=league, date=day))))
            read += 1
        except Exception as e:
            log(f"backup scoreboard: {day} could not be read: {e!r}"[:200])
    if not read:
        raise RuntimeError("neither the scoreboard nor the backup scoreboard could be reached")
    changed = 0
    for g in sorted(due, key=lambda g: g["start"]):
        y, flip = find(g, listed)
        if not y or not y["state"]:
            continue
        y["used"] = True
        g["backup"] = {"periods": y["periods"], "shootout": y["shootout"]}     # for the caller; not stored
        away, home = (y["home"], y["away"]) if flip else (y["away"], y["home"])
        if away["score"] is None or home["score"] is None:
            continue
        before = (g["state"], g["away"].get("score"), g["home"].get("score"))
        g["state"], g["away"]["score"], g["home"]["score"] = y["state"], away["score"], home["score"]
        if y["state"] == "live":
            g["detail"] = y["detail"] or g.get("detail") or ""
        else:
            g.pop("detail", None)
        changed += before != (g["state"], away["score"], home["score"])
    log(f"backup scoreboard: the usual feed could not be read; {changed} of {len(due)} games brought up to date from Yahoo")
    return {"days": read, "changed": changed}

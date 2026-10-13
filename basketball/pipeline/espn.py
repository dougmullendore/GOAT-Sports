"""Reading ESPN's feeds: the schedule, the rankings, the standings, a game's
box score, a team's roster and a player's career."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from . import config

_WEST = ZoneInfo(config.GAME_TIMEZONE)
_EAST = ZoneInfo("America/New_York")


def _int(v, default=0):
    try:
        return int(float(str(v).replace(",", "").replace("+", "")))
    except (TypeError, ValueError):
        return default


def _pair(v) -> tuple[int, int]:
    """'13-22' as (13, 22)."""
    a, _, b = str(v or "").replace("/", "-").partition("-")
    return _int(a), _int(b)


def real_team(team: dict) -> bool:
    """False for the "TBD" a tournament game shows until its teams are known."""
    return str(team.get("id") or "").isdigit()


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ------------------------------------------------------------ the schedule --
def parse_season(doc: dict) -> tuple[int | None, str, str]:
    """(season, first day, last day) from the scoreboard: the season is named by the year it
    ends in (2027 for 2026-27), and the days are those that can have a game."""
    league = ((doc or {}).get("leagues") or [{}])[0]
    season = (league.get("season") or {}).get("year")
    listed = sorted(str(d)[:10] for d in league.get("calendar") or [] if isinstance(d, str))
    first = (league.get("calendarStartDate") or (league.get("season") or {}).get("startDate") or "")[:10]
    last = (league.get("calendarEndDate") or (league.get("season") or {}).get("endDate") or "")[:10]
    if listed and (not first or listed[0] > first):
        first = listed[0]               # nothing is played before the first day the calendar lists
    return season, first, last


def parse_event(e: dict, day: str) -> dict | None:
    """One game from a day's scoreboard, or None if it is not one the site lists: a
    preseason game, or a tournament game whose teams are not known yet. `day` is the
    day ESPN lists it under (YYYYMMDD)."""
    comp = (e.get("competitions") or [{}])[0]
    sides = {c.get("homeAway"): c for c in comp.get("competitors") or []}
    home, away = sides.get("home"), sides.get("away")
    kind = _int((e.get("season") or {}).get("type"), 2)
    if kind not in (2, 3) and not (kind == 1 and config.PRESEASON_GAMES):
        return None                     # preseason (unless listed), all-star weekend
    if not home or not away or not e.get("id") or not real_team(home.get("team") or {}) or not real_team(away.get("team") or {}):
        return None
    try:
        when = dt.datetime.fromisoformat((e.get("date") or comp.get("date") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    timed = comp.get("timeValid", True) is not False and not (when.minute == 0 and when.hour in (4, 5) and (e.get("status") or {}).get("type", {}).get("state") == "pre")
    # With no tip-off time set, ESPN gives midnight in the east on the day of the game.
    date = when.astimezone(_WEST if timed else _EAST).date().isoformat()
    st = (e.get("status") or {}).get("type") or {}
    name = st.get("name") or ""
    if st.get("state") == "post" and st.get("completed"):
        state = "final"
    elif st.get("state") == "in":
        state = "live"
    elif name in ("STATUS_SCHEDULED", "STATUS_DELAYED") or st.get("state") == "pre" and name not in ("STATUS_CANCELED", "STATUS_POSTPONED"):
        state = "upcoming"
    else:
        state = "other"

    def side(c):
        t = c["team"]
        score = c.get("score")
        out = {"id": str(t["id"]), "name": t.get(config.TEAM_NAME) or t.get("location") or t.get("shortDisplayName") or t.get("displayName") or str(t["id"]),
               "abbr": t.get("abbreviation") or "",
               "score": _int(score) if state in ("final", "live") and str(score or "").strip() != "" else None}
        lines = [_int(x.get("value")) for x in c.get("linescores") or []]
        if lines and state in ("final", "live"):
            out["lines"] = lines
        return out

    g = {"id": int(e["id"]), "date": date, "start": int(when.timestamp()) if timed else None, "state": state,
         "note": "" if state != "other" else (st.get("description") or "not played").lower(),
         "round": next((n.get("headline") or "" for n in comp.get("notes") or [] if n.get("type") == "event"), ""),
         "day": day, "kind": kind, "away": side(away), "home": side(home)}
    if comp.get("neutralSite"):
        g["neutral"] = 1
    if comp.get("conferenceCompetition"):
        g["conf"] = 1
    if state == "live":
        g["detail"] = st.get("shortDetail") or st.get("detail") or ""
    tv = [n for b in comp.get("broadcasts") or [] for n in b.get("names") or []]
    if tv:
        national = [n for b in comp.get("broadcasts") or [] if b.get("market") == "national" for n in b.get("names") or []]
        g["tv"] = (national or tv)[:3]
    odds = next((o for o in comp.get("odds") or [] if o and o.get("details")), None)
    if odds and state != "final":
        g["line"] = [odds.get("details"), odds.get("overUnder"), (odds.get("provider") or {}).get("name")]   # the betting line: "DUKE -7.5", the total, and the sportsbook
    series = comp.get("series") or {}
    if kind == 3 and series.get("summary"):
        g["series"] = series["summary"]                                 # "BOS leads series 2-1"
    return g


# ------------------------------------------------------------ the rankings --
def parse_rankings(doc: dict) -> dict:
    """{poll type: {"date", "season", "name", "week", "rows": [{rank, id, name, prev, points, votes, record}]}}
    for the rankings ESPN carries. `date` is the day the ranking came out and
    `season` the season it belongs to."""
    out = {}
    for r in (doc or {}).get("rankings") or []:
        kind = r.get("type")
        if kind not in (config.POLL_TYPE, *config.OTHER_POLLS):
            continue
        rows = []
        for x in r.get("ranks") or []:
            t = x.get("team") or {}
            if not x.get("current") or not real_team(t):
                continue
            rows.append({"rank": int(x["current"]), "id": str(t["id"]), "name": t.get("location") or t.get("nickname") or "",
                         "prev": int(x["previous"]) if x.get("previous") else None,
                         "points": _int(x.get("points"), None) if x.get("points") else None,
                         "votes": _int(x.get("firstPlaceVotes")), "record": x.get("recordSummary") or ""})
        rows.sort(key=lambda x: x["rank"])
        date = (r.get("date") or "")[:10]
        if rows and date:
            out[kind] = {"date": date, "season": (r.get("season") or {}).get("year"), "name": r.get("name") or kind,
                         "week": (r.get("occurrence") or {}).get("displayValue") or "", "rows": rows}
    return out


# ----------------------------------------------------------- the standings --
def parse_standings(doc: dict) -> dict:
    """Every team of the league (every Division I team; every NBA team):
    {team id: {"name", "abbr", "nick", "place", "conf", "group", "logo", "w", "l", "t", "pf", "pa", "seed", "gb",
               "rec": {"all", "home", "away", "conf", "div", "ranked", "streak", "last10"}}}
    `conf` is what the team is grouped under on the site: its conference in
    college ("ACC"), its division in the NBA ("Atlantic", with `group` "East")."""
    out = {}

    def walk(node, top, conf):
        for e in (node.get("standings") or {}).get("entries") or []:
            t = e.get("team") or {}
            if not real_team(t):
                continue
            stats = {}
            for s in e.get("stats") or []:
                stats.setdefault(s.get("type") or s.get("name"), s)

            def rec(*keys):
                for key in keys:
                    v = (stats.get(key) or {}).get("summary") or (stats.get(key) or {}).get("displayValue")
                    if v:
                        return v
                return ""

            def num(key):
                return _int((stats.get(key) or {}).get("value", (stats.get(key) or {}).get("displayValue")))

            w, l = num("wins"), num("losses")
            out[str(t["id"])] = {"name": t.get(config.TEAM_NAME) or t.get("location") or t.get("displayName") or "",
                                 "abbr": t.get("abbreviation") or "", "nick": t.get("name") or "", "place": t.get("location") or "",
                                 "conf": conf, "group": top if conf != top else "",
                                 "logo": next((x.get("href") for x in t.get("logos") or [] if x.get("href")), ""),
                                 "w": w, "l": l, "t": 0, "pf": num("pointsfor"), "pa": num("pointsagainst"),
                                 "seed": num("playoffseed"), "gb": rec("gamesbehind"),
                                 "rec": {"all": rec("total") or f"{w}-{l}", "home": rec("home", "homerecord"), "away": rec("road", "awayrecord"),
                                         "conf": rec("vsconf"), "div": rec("vsdiv"), "ranked": rec("vsaprankedteams"),
                                         "streak": rec("streak"), "last10": rec("lasttengames")}}
        for child in node.get("children") or []:
            # College: a division belongs to its conference. The NBA: a division is the group.
            walk(child, top, (child.get("name") or conf) if config.POLL_TYPE is None else conf)

    for top in (doc or {}).get("children") or []:
        name = top.get("shortName") or top.get("abbreviation") or (top.get("name") or "").replace("ern Conference", "").replace(" Conference", "")
        walk(top, name, name)
    return out


# ------------------------------------------------------------- a box score --
# One row per player per game: [player id, name, shirt number, position, started] and then these.
COLS = ["min", "pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "ast", "to", "stl", "blk", "oreb", "dreb", "pf", "pm"]
_FEED = {"min": "minutes", "pts": "points", "fgm": ("fieldGoalsMade-fieldGoalsAttempted", 0), "fga": ("fieldGoalsMade-fieldGoalsAttempted", 1),
         "tpm": ("threePointFieldGoalsMade-threePointFieldGoalsAttempted", 0), "tpa": ("threePointFieldGoalsMade-threePointFieldGoalsAttempted", 1),
         "ftm": ("freeThrowsMade-freeThrowsAttempted", 0), "fta": ("freeThrowsMade-freeThrowsAttempted", 1),
         "reb": "rebounds", "ast": "assists", "to": "turnovers", "stl": "steals", "blk": "blocks",
         "oreb": "offensiveRebounds", "dreb": "defensiveRebounds", "pf": "fouls", "pm": "plusMinus"}
# A team's totals for a game, in this order.
TEAM = ["fgm", "fga", "tpm", "tpa", "ftm", "fta", "reb", "oreb", "dreb", "ast", "stl", "blk", "to", "pf"]
_TEAM_FEED = {"fgm": ("fieldGoalsMade-fieldGoalsAttempted", 0), "fga": ("fieldGoalsMade-fieldGoalsAttempted", 1),
              "tpm": ("threePointFieldGoalsMade-threePointFieldGoalsAttempted", 0), "tpa": ("threePointFieldGoalsMade-threePointFieldGoalsAttempted", 1),
              "ftm": ("freeThrowsMade-freeThrowsAttempted", 0), "fta": ("freeThrowsMade-freeThrowsAttempted", 1),
              "reb": "totalRebounds", "oreb": "offensiveRebounds", "dreb": "defensiveRebounds", "ast": "assists", "stl": "steals",
              "blk": "blocks", "to": "totalTurnovers", "pf": "fouls"}


def _value(raw_by_key: dict, key) -> int:
    if isinstance(key, tuple):
        return _pair(raw_by_key.get(key[0]))[key[1]]
    return _int(raw_by_key.get(key))


def parse_summary(doc: dict) -> dict:
    """A game's box score, cut down to what the site uses:
    {"status": "F" final / "L" under way / "" not started,
     "home_id", "away_id",
     "team": {"home": [numbers in TEAM order], "away": [...]},
     "players": {"home": [[id, name, number, position, started, ...COLS], ...], "away": [...]}}
    Only players who got on the court are kept."""
    doc = doc or {}
    comp = ((doc.get("header") or {}).get("competitions") or [{}])[0]
    side_of = {str((c.get("team") or {}).get("id")): c.get("homeAway") for c in comp.get("competitors") or []}
    st = (comp.get("status") or {}).get("type") or {}
    status = "F" if st.get("state") == "post" and st.get("completed") else "L" if st.get("state") == "in" else ""
    ids = {v: k for k, v in side_of.items()}
    out = {"status": status, "home_id": ids.get("home"), "away_id": ids.get("away"), "team": {}, "players": {"home": [], "away": []}}
    box = doc.get("boxscore") or {}
    for t in box.get("teams") or []:
        side = side_of.get(str((t.get("team") or {}).get("id"))) or t.get("homeAway")
        raw = {s.get("name"): s.get("displayValue") for s in t.get("statistics") or []}
        if side in ("home", "away") and raw:
            if "totalTurnovers" not in raw:
                raw["totalTurnovers"] = raw.get("turnovers")
            out["team"][side] = [_value(raw, _TEAM_FEED[k]) for k in TEAM]
    for tp in box.get("players") or []:
        side = side_of.get(str((tp.get("team") or {}).get("id")))
        if side not in ("home", "away"):
            continue
        for block in tp.get("statistics") or []:
            keys = block.get("keys") or block.get("names") or []
            for a in block.get("athletes") or []:
                who, stats = a.get("athlete") or {}, a.get("stats") or []
                if not str(who.get("id") or "").isdigit() or a.get("didNotPlay") or not stats:
                    continue
                raw = dict(zip(keys, stats))
                row = [str(who["id"]), who.get("displayName") or "", who.get("jersey") or "",
                       ((who.get("position") or {}).get("abbreviation") or "").upper(), 1 if a.get("starter") else 0]
                row += [_value(raw, _FEED[c]) for c in COLS]
                if row[5 + COLS.index("min")] > 0 or any(row[6:]):
                    out["players"][side].append(row)
    return out


# ---------------------------------------------------------------- a roster --
def parse_roster(doc: dict) -> dict:
    """{player id: [name, number, position, height in inches, weight, class, hometown, has a photo, college]}
    For the NBA, "class" is how long he has been in the league ("Rookie", "4th season") and
    the last item is the college he came from."""
    out = {}
    people = []
    for x in (doc or {}).get("athletes") or []:
        people += x.get("items") or ([x] if x.get("id") else [])       # some sports list players in groups, some do not
    for a in people:
        if not str(a.get("id") or "").isdigit():
            continue
        exp, born = a.get("experience") or {}, a.get("birthPlace") or {}
        year = exp.get("displayValue") or ""
        if not year and config.POLL_TYPE is None and exp.get("years") is not None:
            year = "Rookie" if not exp["years"] else f"{_ordinal(int(exp['years']) + 1)} season"
        home = born.get("displayText") or ", ".join(x for x in (born.get("city"), born.get("state") or born.get("country")) if x)
        out[str(a["id"])] = [a.get("displayName") or a.get("fullName") or "", a.get("jersey") or "",
                             ((a.get("position") or {}).get("abbreviation") or "").upper(),
                             _int(a.get("height"), None) if a.get("height") else None, _int(a.get("weight"), None) if a.get("weight") else None,
                             year, home, 1 if (a.get("headshot") or {}).get("href") else 0,
                             ((a.get("college") or {}).get("name") or "") if config.POLL_TYPE is None else ""]
    return out


# ---------------------------------------------------------------- a career --
def parse_career(doc: dict) -> list:
    """A player's seasons as ESPN lists them:
    [[part, [column headings], [[season, team, numbers...], ...], [career numbers...]], ...]"""
    teams = {str(t.get("id")): t.get("abbreviation") or t.get("location") or "" for t in ((doc or {}).get("teams") or {}).values()}
    out = []
    for cat in (doc or {}).get("categories") or []:
        rows = [[(s.get("season") or {}).get("displayName") or (s.get("season") or {}).get("year"), teams.get(str(s.get("teamId")), "")] + [str(v) for v in s.get("stats") or []]
                for s in cat.get("statistics") or [] if (s.get("season") or {}).get("year")]
        if rows:
            out.append([cat.get("displayName") or cat.get("name") or "", [str(x).strip() for x in cat.get("labels") or []],
                        rows, [str(v) for v in cat.get("totals") or []]])
    return out

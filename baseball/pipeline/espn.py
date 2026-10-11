"""Reading ESPN's feeds: the schedule, the standings, a game's
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
    """(season, first day, last day) from the scoreboard. The days are those that can have a
    game, spring training included (its games are passed over as each day is read)."""
    league = ((doc or {}).get("leagues") or [{}])[0]
    season = (league.get("season") or {}).get("year")
    first = (league.get("calendarStartDate") or (league.get("season") or {}).get("startDate") or "")[:10]
    last = (league.get("calendarEndDate") or (league.get("season") or {}).get("endDate") or "")[:10]
    return season, first, last


def parse_event(e: dict, day: str) -> dict | None:
    """One game from a day's scoreboard, or None if it is not one the site lists: a
    spring training game, the all-star game, or a playoff game whose teams are not known yet. `day` is the
    day ESPN lists it under (YYYYMMDD)."""
    comp = (e.get("competitions") or [{}])[0]
    sides = {c.get("homeAway"): c for c in comp.get("competitors") or []}
    home, away = sides.get("home"), sides.get("away")
    kind = _int((e.get("season") or {}).get("type"), 2)
    if kind not in (2, 3):
        return None                     # spring training, the all-star game
    if not home or not away or not e.get("id") or not real_team(home.get("team") or {}) or not real_team(away.get("team") or {}):
        return None
    try:
        when = dt.datetime.fromisoformat((e.get("date") or comp.get("date") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    timed = comp.get("timeValid", True) is not False and not (when.minute == 0 and when.hour in (4, 5) and (e.get("status") or {}).get("type", {}).get("state") == "pre")
    # With no start time set, ESPN gives midnight in the east on the day of the game.
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
        if state == "upcoming":
            who = next((x.get("athlete") or {} for x in c.get("probables") or [] if x.get("name") == "probableStartingPitcher"), {})
            if who.get("displayName") or who.get("shortName"):
                out["sp"] = [str(who.get("id") or ""), who.get("shortName") or who.get("displayName")]      # who is expected to start
        return out

    g = {"id": int(e["id"]), "date": date, "start": int(when.timestamp()) if timed else None, "state": state,
         "note": "" if state != "other" else (st.get("description") or "not played").lower(),
         "round": next((n.get("headline") or "" for n in comp.get("notes") or [] if n.get("type") == "event"), ""),
         "day": day, "kind": kind, "away": side(away), "home": side(home)}
    if comp.get("neutralSite"):
        g["neutral"] = 1
    if comp.get("conferenceCompetition"):
        g["conf"] = 1
    if state in ("final", "live"):
        g["extra"] = [[_int(c.get("hits")), _int(c.get("errors"))] for c in (away, home)]      # hits and errors, for the line score
        for who in ((comp.get("status") or {}).get("featuredAthletes") or []):
            key = {"winningPitcher": "wp", "losingPitcher": "lp", "savingPitcher": "sv"}.get(who.get("name"))
            a = who.get("athlete") or {}
            if key and state == "final" and a.get("id"):
                g[key] = [str(a["id"]), a.get("shortName") or a.get("displayName") or ""]
    if state == "live":
        g["detail"] = st.get("shortDetail") or st.get("detail") or ""
    tv = [n for b in comp.get("broadcasts") or [] for n in b.get("names") or []]
    if tv:
        national = [n for b in comp.get("broadcasts") or [] if b.get("market") == "national" for n in b.get("names") or []]
        g["tv"] = (national or tv)[:3]
    odds = next((o for o in comp.get("odds") or [] if o and o.get("details")), None)
    if odds and state != "final":
        g["line"] = [odds.get("details"), odds.get("overUnder")]       # the betting line: "NYY -150", and the total
    series = comp.get("series") or {}
    if kind == 3 and series.get("summary"):
        g["series"] = series["summary"]                                 # "NYY leads series 2-1"
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
    """Every team of the league:
    {team id: {"name", "abbr", "nick", "place", "conf", "group", "logo", "w", "l", "t", "pf", "pa", "seed", "gb",
               "rec": {"all", "home", "away", "conf", "div", "ranked", "streak", "last10"}}}
    `conf` is what the team is grouped under on the site, its division ("AL East"), and
    `group` its league ("AL")."""
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
                                 "seed": num("playoffseed"), "gb": rec("divisiongamesbehind", "gamesbehind"),
                                 "rec": {"all": rec("total") or f"{w}-{l}", "home": rec("home", "homerecord"), "away": rec("road", "awayrecord"),
                                         "conf": rec("intraleague", "vsconf"), "div": rec("intradivision", "vsdiv"), "ranked": "",
                                         "streak": rec("streak"), "last10": rec("lasttengames")}}
        for child in node.get("children") or []:
            walk(child, top, child.get("shortName") or child.get("name") or conf)

    for top in (doc or {}).get("children") or []:
        name = top.get("abbreviation") or top.get("shortName") or top.get("name") or ""
        walk(top, name, name)
    return out


# ------------------------------------------------------------- a box score --
# One row per player per game: [player id, name, pitcher's decision ("W", "L", "S", "H" or ""),
# position, started] and then these. A man who only batted has no pitching numbers and a
# pitcher usually has no batting numbers.
#   batting:  bo is his place in the batting order (1 to 9; 0 for a pitcher who did not bat),
#             avg, obp and slg are his season's figures after this game, in thousandths (ESPN's
#             own: a box score does not say which hits were doubles or triples, or who was hit by a pitch)
#   pitching: pn is his turn on the mound (1 for the starter; 0 if he did not pitch), outs is
#             outs recorded (three to an inning), era his season's figure in hundredths
COLS = ["bo", "ab", "r", "h", "rbi", "hr", "bb", "k", "avg", "obp", "slg",
        "pn", "outs", "ph", "pr", "er", "pbb", "pk", "phr", "pc", "era"]
_BAT = {"ab": "atBats", "r": "runs", "h": "hits", "rbi": "RBIs", "hr": "homeRuns", "bb": "walks", "k": "strikeouts"}
_PIT = {"ph": "hits", "pr": "runs", "er": "earnedRuns", "pbb": "walks", "pk": "strikeouts", "phr": "homeRuns", "pc": "pitches"}
POSITION = {"Pitcher": "P", "Starting Pitcher": "SP", "Relief Pitcher": "RP", "Catcher": "C", "First Baseman": "1B", "Second Baseman": "2B",
            "Third Baseman": "3B", "Shortstop": "SS", "Left Fielder": "LF", "Center Fielder": "CF", "Right Fielder": "RF",
            "Designated Hitter": "DH", "Pinch Hitter": "PH", "Pinch Runner": "PR", "Infielder": "IF", "Outfielder": "OF"}
# A team's totals for a game, in this order: its batting, then its pitching, then its fielding.
TEAM = ["ab", "r", "h", "d", "t", "hr", "rbi", "bb", "k", "hbp", "sf", "sb", "cs", "lob", "tb", "pa",
        "outs", "ph", "pr", "er", "pbb", "pk", "phr", "bf", "e", "dp"]
_TEAM_FEED = {"batting": {"ab": "atBats", "r": "runs", "h": "hits", "d": "doubles", "t": "triples", "hr": "homeRuns", "rbi": "RBIs", "bb": "walks",
                          "k": "strikeouts", "hbp": "hitByPitch", "sf": "sacFlies", "sb": "stolenBases", "cs": "caughtStealing",
                          "lob": "runnersLeftOnBase", "tb": "totalBases", "pa": "plateAppearances"},
              "pitching": {"outs": "thirdInnings", "ph": "hits", "pr": "runs", "er": "earnedRuns", "pbb": "walks", "pk": "strikeouts",
                           "phr": "homeRuns", "bf": "battersFaced"},
              "fielding": {"e": "errors", "dp": "doublePlays"}}


def outs(innings) -> int:
    """Innings pitched as outs: "6.2" is six innings and two outs, 20."""
    whole, _, part = str(innings or "0").partition(".")
    return 3 * _int(whole) + min(2, _int(part[:1]))


def _thousandths(v, scale=1000) -> int:
    try:
        return round(min(float(v), 99.99) * scale)      # an earned run average can be "INF": runs in, nobody out
    except (TypeError, ValueError):
        return 0


def parse_summary(doc: dict) -> dict:
    """A game's box score, cut down to what the site uses:
    {"status": "F" final / "L" under way / "" not started,
     "home_id", "away_id",
     "team": {"home": [numbers in TEAM order], "away": [...]},
     "players": {"home": [[id, name, decision, position, started, ...COLS], ...], "away": [...]}}
    Batters come first, in batting order with each substitute after the man he replaced,
    then any pitchers who did not bat, in the order they pitched."""
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
        raw = {g.get("name"): {s.get("name"): s.get("displayValue") for s in g.get("stats") or []} for g in t.get("statistics") or []}
        if side in ("home", "away") and raw.get("batting"):
            out["team"][side] = [_int((raw.get(group) or {}).get(key)) for group, keys in _TEAM_FEED.items() for key in keys.values()]
    at = {c: 5 + i for i, c in enumerate(COLS)}
    for tp in box.get("players") or []:
        side = side_of.get(str((tp.get("team") or {}).get("id")))
        if side not in ("home", "away"):
            continue
        rows, order = {}, []
        for block in tp.get("statistics") or []:
            keys = block.get("keys") or []
            pitching = "fullInnings.partInnings" in keys
            turn = 0
            for a in block.get("athletes") or []:
                who, stats = a.get("athlete") or {}, a.get("stats") or []
                if not str(who.get("id") or "").isdigit() or not stats:
                    continue
                raw = dict(zip(keys, stats))
                pid = str(who["id"])
                if pid not in rows:
                    where = (a.get("position") or {})
                    rows[pid] = [pid, who.get("displayName") or "", "", where.get("abbreviation") or POSITION.get(where.get("displayName") or "", ""), 0] + [0] * len(COLS)
                    order.append(pid)
                row = rows[pid]
                if pitching:
                    turn += 1
                    row[at["pn"]] = turn
                    row[at["outs"]] = outs(raw.get("fullInnings.partInnings"))
                    for c, k in _PIT.items():
                        row[at[c]] = _int(raw.get(k))
                    row[at["era"]] = _thousandths(raw.get("ERA"), 100)
                    row[2] = next(((n.get("text") or "")[:1] for n in a.get("notes") or [] if n.get("type") == "pitchingDecision"), "")
                    if turn == 1:
                        row[4] = 1
                        if row[3] in ("", "P"):
                            row[3] = "SP"
                    elif row[3] in ("", "P"):
                        row[3] = "RP"
                else:
                    row[at["bo"]] = _int(a.get("batOrder"))
                    for c, k in _BAT.items():
                        row[at[c]] = _int(raw.get(k))
                    row[at["avg"]], row[at["obp"]], row[at["slg"]] = _thousandths(raw.get("avg")), _thousandths(raw.get("onBasePct")), _thousandths(raw.get("slugAvg"))
                    if a.get("starter"):
                        row[4] = 1
        out["players"][side] = [rows[pid] for pid in order]
    return out


# ---------------------------------------------------------------- a roster --
def parse_roster(doc: dict) -> dict:
    """{player id: [name, number, position, height in inches, weight, time in the league, hometown,
    has a photo, bats and throws ("L/R")]}. Time in the league is "Rookie" or "4th season"."""
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
                             "/".join(x for x in ((a.get("bats") or {}).get("abbreviation"), (a.get("throws") or {}).get("abbreviation")) if x)]
    return out


# ---------------------------------------------------------------- a career --
def parse_career(doc: dict) -> list:
    """A player's seasons as ESPN lists them:
    [[part, [column headings], [[season, team, numbers...], ...], [career numbers...]], ...]"""
    teams = {str(t.get("id")): t.get("abbreviation") or t.get("location") or "" for t in ((doc or {}).get("teams") or {}).values()}
    out = []
    for cat in (doc or {}).get("categories") or []:
        if not str(cat.get("name") or "").startswith(("career-", "postseason-")):
            continue                    # the main tables only: ESPN lists a dozen more
        rows = [[(s.get("season") or {}).get("displayName") or (s.get("season") or {}).get("year"), teams.get(str(s.get("teamId")), "")] + [str(v) for v in s.get("stats") or []]
                for s in cat.get("statistics") or [] if (s.get("season") or {}).get("year")]
        if rows:
            out.append([cat.get("displayName") or cat.get("name") or "", [str(x).strip() for x in cat.get("labels") or []],
                        rows, [str(v) for v in cat.get("totals") or []]])
    return out

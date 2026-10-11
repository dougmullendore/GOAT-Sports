"""Reading ESPN's feeds: the schedule, the rankings, the conferences, a game's
box score, a team's roster and a player's career."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from . import config

_WEST = ZoneInfo(config.GAME_TIMEZONE)
_EAST = ZoneInfo("America/New_York")


def _int(v, default=0):
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return default


def _num(v, default=0.0):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _pair(v) -> tuple[int, int]:
    """'19/31' or '8-61' as (19, 31)."""
    a, _, b = str(v or "").replace("/", "-").partition("-")
    return _int(a), _int(b)


def real_team(team: dict) -> bool:
    """False for the "TBD" a bowl game shows until its teams are chosen."""
    return str(team.get("id") or "").isdigit()


# ------------------------------------------------------------ the schedule --
def parse_calendar(doc: dict) -> tuple[int | None, list[list]]:
    """(season, [[kind, week, label, first day, last day], ...]) from any scoreboard.
    Kind 2 is the regular season and 3 the bowls and the playoff."""
    league = ((doc or {}).get("leagues") or [{}])[0]
    season = (league.get("season") or {}).get("year")
    weeks = []
    for part in league.get("calendar") or []:
        if not isinstance(part, dict) or str(part.get("value")) not in ("2", "3"):
            continue
        for e in part.get("entries") or []:
            weeks.append([int(part["value"]), _int(e.get("value")), e.get("label") or f"Week {e.get('value')}",
                          (e.get("startDate") or "")[:10], (e.get("endDate") or "")[:10]])
    return season, weeks


def parse_event(e: dict, kind: int, week: int) -> dict | None:
    """One game from a scoreboard, or None if it is unusable (a bowl whose teams are not chosen yet)."""
    comp = (e.get("competitions") or [{}])[0]
    sides = {c.get("homeAway"): c for c in comp.get("competitors") or []}
    home, away = sides.get("home"), sides.get("away")
    if not home or not away or not e.get("id") or not real_team(home.get("team") or {}) or not real_team(away.get("team") or {}):
        return None
    try:
        when = dt.datetime.fromisoformat((e.get("date") or comp.get("date") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    timed = bool(comp.get("timeValid"))
    # With no kickoff time set, ESPN gives midnight in the east on the day of the game.
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
        out = {"id": str(t["id"]), "name": t.get("location") or t.get("shortDisplayName") or t.get("displayName") or str(t["id"]),
               "abbr": t.get("abbreviation") or "",
               "score": _int(score) if state in ("final", "live") and str(score or "").strip() != "" else None}
        lines = [_int(x.get("value")) for x in c.get("linescores") or []]
        if lines and state in ("final", "live"):
            out["lines"] = lines
        return out

    g = {"id": int(e["id"]), "date": date, "start": int(when.timestamp()) if timed else None, "state": state,
         "note": "" if state != "other" else (st.get("description") or "not played").lower(),
         "round": next((n.get("headline") or "" for n in comp.get("notes") or [] if n.get("type") == "event"), "") if kind == 3 else "",
         "week": [kind, week], "away": side(away), "home": side(home)}
    if comp.get("neutralSite"):
        g["neutral"] = 1
    if comp.get("conferenceCompetition"):
        g["conf"] = 1
    if state == "live":
        g["detail"] = st.get("shortDetail") or st.get("detail") or ""
    tv = [n for b in comp.get("broadcasts") or [] for n in b.get("names") or []]
    if tv:
        g["tv"] = tv[:3]
    odds = next((o for o in comp.get("odds") or [] if o and o.get("details")), None)
    if odds and state != "final":
        g["line"] = [odds.get("details"), odds.get("overUnder")]       # the betting line: "TEX -7.5", and the total
    return g


# ------------------------------------------------------------ the rankings --
def parse_rankings(doc: dict) -> dict:
    """{poll type: {"date", "name", "week", "rows": [{rank, id, name, prev, points, votes, record}]}}
    for the FBS rankings ESPN carries. `date` is the day the ranking came out."""
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
            out[kind] = {"date": date, "name": r.get("name") or kind, "week": (r.get("occurrence") or {}).get("displayValue") or "", "rows": rows}
    return out


# --------------------------------------------------------- the conferences --
def parse_standings(doc: dict) -> dict:
    """{team id: {"name", "abbr", "nick", "conf", "rec": {...}}} for every FBS team."""
    out = {}

    def walk(node, conf):
        for e in (node.get("standings") or {}).get("entries") or []:
            t = e.get("team") or {}
            if not real_team(t):
                continue
            stats = {s.get("type") or s.get("name"): s for s in e.get("stats") or []}

            def rec(key):
                return (stats.get(key) or {}).get("summary") or (stats.get(key) or {}).get("displayValue") or ""

            out[str(t["id"])] = {"name": t.get("location") or t.get("displayName") or "", "abbr": t.get("abbreviation") or "",
                                 "nick": t.get("name") or "", "conf": conf,
                                 "rec": {"all": rec("total"), "home": rec("homerecord"), "away": rec("awayrecord"),
                                         "conf": rec("vsconf"), "ranked": rec("vsaprankedteams"), "streak": rec("streak")}}
        for child in node.get("children") or []:
            walk(child, conf)                 # a division ("Sun Belt - East") belongs to its conference

    for top in (doc or {}).get("children") or []:
        walk(top, top.get("shortName") or top.get("abbreviation") or top.get("name") or "")
    return out


# ------------------------------------------------------------- a box score --
# What is kept for each player, by the part of the box score it comes from. Each row starts
# [player id, name, shirt number] and then has these numbers in this order.
CATS = {
    "passing": ["cmp", "att", "yds", "td", "int"],
    "rushing": ["car", "yds", "td", "long"],
    "receiving": ["rec", "yds", "td", "long"],
    "fumbles": ["fum", "lost", "rec"],
    "defensive": ["tkl", "solo", "sk", "tfl", "pd", "hur", "td"],
    "interceptions": ["int", "yds", "td"],
    "kickReturns": ["no", "yds", "long", "td"],
    "puntReturns": ["no", "yds", "long", "td"],
    "kicking": ["fgm", "fga", "long", "xpm", "xpa", "pts"],
    "punting": ["no", "yds", "tb", "in20", "long"],
}
_FEED = {     # our name for a number: ESPN's key for it ("a/b" keys are split in two)
    "passing": {"cmp": ("completions/passingAttempts", 0), "att": ("completions/passingAttempts", 1), "yds": "passingYards",
                "td": "passingTouchdowns", "int": "interceptions"},
    "rushing": {"car": "rushingAttempts", "yds": "rushingYards", "td": "rushingTouchdowns", "long": "longRushing"},
    "receiving": {"rec": "receptions", "yds": "receivingYards", "td": "receivingTouchdowns", "long": "longReception"},
    "fumbles": {"fum": "fumbles", "lost": "fumblesLost", "rec": "fumblesRecovered"},
    "defensive": {"tkl": "totalTackles", "solo": "soloTackles", "sk": "sacks", "tfl": "tacklesForLoss", "pd": "passesDefended",
                  "hur": "hurries", "td": "defensiveTouchdowns"},
    "interceptions": {"int": "interceptions", "yds": "interceptionYards", "td": "interceptionTouchdowns"},
    "kickReturns": {"no": "kickReturns", "yds": "kickReturnYards", "long": "longKickReturn", "td": "kickReturnTouchdowns"},
    "puntReturns": {"no": "puntReturns", "yds": "puntReturnYards", "long": "longPuntReturn", "td": "puntReturnTouchdowns"},
    "kicking": {"fgm": ("fieldGoalsMade/fieldGoalAttempts", 0), "fga": ("fieldGoalsMade/fieldGoalAttempts", 1), "long": "longFieldGoalMade",
                "xpm": ("extraPointsMade/extraPointAttempts", 0), "xpa": ("extraPointsMade/extraPointAttempts", 1), "pts": "totalKickingPoints"},
    "punting": {"no": "punts", "yds": "puntYards", "tb": "touchbacks", "in20": "puntsInside20", "long": "longPunt"},
}
HALVES = {"sk", "tfl"}          # these can be shared: half a sack
# A team's totals for a game, in this order.
TEAM = ["fd", "yds", "pyds", "cmp", "att", "ryds", "car", "c3", "a3", "c4", "a4", "pen", "penyds", "to", "fuml", "int", "top",
        "drives", "scores", "tds"]


def _team_stats(stats: list) -> dict:
    by = {s.get("name"): s for s in stats or []}

    def val(key):
        return (by.get(key) or {}).get("displayValue")

    cmp_, att = _pair(val("completionAttempts"))
    c3, a3 = _pair(val("thirdDownEff"))
    c4, a4 = _pair(val("fourthDownEff"))
    pen, penyds = _pair(val("totalPenaltiesYards"))
    top = val("possessionTime") or ""
    mins, _, secs = top.partition(":")
    return {"fd": _int(val("firstDowns")), "yds": _int(val("totalYards")), "pyds": _int(val("netPassingYards")), "cmp": cmp_, "att": att,
            "ryds": _int(val("rushingYards")), "car": _int(val("rushingAttempts")), "c3": c3, "a3": a3, "c4": c4, "a4": a4,
            "pen": pen, "penyds": penyds, "to": _int(val("turnovers")), "fuml": _int(val("fumblesLost")), "int": _int(val("interceptions")),
            "top": _int(mins) * 60 + _int(secs)}


def parse_summary(doc: dict) -> dict:
    """A game's box score, cut down to what the site uses:
    {"status": "F" final / "L" under way / "" not started,
     "home_id", "away_id",
     "team": {"home": [numbers in TEAM order], "away": [...]},
     "players": {"home": {part: [[id, name, number, ...], ...]}, "away": {...}},
     "scoring": [[quarter, clock, "home"/"away", kind, words, away score, home score], ...]}"""
    doc = doc or {}
    comp = ((doc.get("header") or {}).get("competitions") or [{}])[0]
    side_of = {str((c.get("team") or {}).get("id")): c.get("homeAway") for c in comp.get("competitors") or []}
    st = (comp.get("status") or {}).get("type") or {}
    status = "F" if st.get("state") == "post" and st.get("completed") else "L" if st.get("state") == "in" else ""
    ids = {v: k for k, v in side_of.items()}
    out = {"status": status, "home_id": ids.get("home"), "away_id": ids.get("away"), "team": {}, "players": {"home": {}, "away": {}}, "scoring": []}
    box = doc.get("boxscore") or {}
    totals = {}
    for t in box.get("teams") or []:
        side = side_of.get(str((t.get("team") or {}).get("id"))) or t.get("homeAway")
        if side in ("home", "away") and t.get("statistics"):
            totals[side] = _team_stats(t["statistics"])
    # each team's drives: how many, and how many ended in points
    for side in totals:
        totals[side].update(drives=0, scores=0, tds=0)
    for d in (doc.get("drives") or {}).get("previous") or []:
        side = side_of.get(str((d.get("team") or {}).get("id")))
        result = (d.get("result") or "").upper()
        if side not in totals or result.startswith("END OF") and not d.get("offensivePlays"):
            continue
        totals[side]["drives"] += 1
        if result in ("TD", "FG"):
            totals[side]["scores"] += 1
            totals[side]["tds"] += result == "TD"
    out["team"] = {side: [t[k] for k in TEAM] for side, t in totals.items()}
    for tp in box.get("players") or []:
        side = side_of.get(str((tp.get("team") or {}).get("id")))
        if side not in ("home", "away"):
            continue
        for cat in tp.get("statistics") or []:
            want = _FEED.get(cat.get("name"))
            if not want:
                continue
            at = {k: i for i, k in enumerate(cat.get("keys") or [])}
            rows = []
            for a in cat.get("athletes") or []:
                who, stats = a.get("athlete") or {}, a.get("stats") or []
                if not str(who.get("id") or "").isdigit():
                    continue                              # "Team": a kneel-down or a snap over the punter's head
                row = [str(who["id"]), who.get("displayName") or "", who.get("jersey") or ""]
                for name in CATS[cat["name"]]:
                    key = want[name]
                    part = None
                    if isinstance(key, tuple):
                        key, part = key
                    raw = stats[at[key]] if key in at and at[key] < len(stats) else None
                    if part is not None:
                        row.append(_pair(raw)[part])
                    elif name in HALVES:
                        v = _num(raw)
                        row.append(int(v) if v == int(v) else v)
                    else:
                        row.append(_int(raw))
                rows.append(row)
            if rows:
                out["players"][side][cat["name"]] = rows
    for p in doc.get("scoringPlays") or []:
        side = side_of.get(str((p.get("team") or {}).get("id")))
        out["scoring"].append([(p.get("period") or {}).get("number"), (p.get("clock") or {}).get("displayValue") or "", side or "",
                               (p.get("type") or {}).get("abbreviation") or "", p.get("text") or "", _int(p.get("awayScore")), _int(p.get("homeScore"))])
    return out


# ---------------------------------------------------------------- a roster --
def parse_roster(doc: dict) -> dict:
    """{player id: [name, number, position, height in inches, weight, class, hometown, has a photo]}"""
    out = {}
    for group in (doc or {}).get("athletes") or []:
        for a in group.get("items") or []:
            if not str(a.get("id") or "").isdigit():
                continue
            out[str(a["id"])] = [a.get("displayName") or a.get("fullName") or "", a.get("jersey") or "",
                                 ((a.get("position") or {}).get("abbreviation") or "").upper(),
                                 _int(a.get("height"), None) if a.get("height") else None, _int(a.get("weight"), None) if a.get("weight") else None,
                                 ((a.get("experience") or {}).get("displayValue") or ""), ((a.get("birthPlace") or {}).get("displayText") or ""),
                                 1 if (a.get("headshot") or {}).get("href") else 0]
    return out


# ---------------------------------------------------------------- a career --
def parse_career(doc: dict) -> list:
    """A player's seasons as ESPN lists them:
    [[part, [column headings], [[season, team, numbers...], ...], [career numbers...]], ...]"""
    teams = {str(t.get("id")): t.get("abbreviation") or t.get("location") or "" for t in ((doc or {}).get("teams") or {}).values()}
    out = []
    for cat in (doc or {}).get("categories") or []:
        rows = [[(s.get("season") or {}).get("year"), teams.get(str(s.get("teamId")), "")] + [str(v) for v in s.get("stats") or []]
                for s in cat.get("statistics") or [] if (s.get("season") or {}).get("year")]
        if rows:
            out.append([cat.get("displayName") or cat.get("name") or "", [str(x).strip() for x in cat.get("labels") or []],
                        rows, [str(v) for v in cat.get("totals") or []]])
    return out

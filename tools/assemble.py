"""Put the sports together into one site.

Usage:  python -m tools.assemble <built_dir> <site_dir>

<built_dir> holds what this run built: built/volleyball, built/hockey,
built/football, built/basketball, built/baseball, whichever of them ran. <site_dir> is a copy of the published
site. Each sport built this run replaces its folder there; a sport that was not
rebuilt (a game-night run that found nothing to do) keeps the pages already
published. Then every sport's pages get the bar across the top that switches
between sports, and the front page and its list of the day's games are redone.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_SRC = ROOT / "home"

# The sports, in the order of the bar and of the front page. `pages` are the folders that hold a
# copy of that sport's page (volleyball has one for college and one for each pro league, football
# one for college and one for the NFL, basketball one for college and one for the NBA). `home`
# is the page the sport's tab opens: the pro league, where a sport has a college one too.
SPORTS = [
    {"key": "volleyball", "name": "Volleyball", "pages": ["", "lovb/", "mlv/"]},
    {"key": "hockey", "name": "Hockey", "pages": [""]},
    {"key": "football", "name": "Football", "pages": ["", "nfl/"], "home": "nfl/"},
    {"key": "basketball", "name": "Basketball", "pages": ["", "nba/"], "home": "nba/"},
    {"key": "baseball", "name": "Baseball", "pages": [""]},
]
# The front page's lists: one for each league, in the order shown (a sport's pro league before its
# college one, except volleyball). `score` is the name the
# league's games give a team's score; `game` is the address of a game's own page; `ranked_only`
# keeps a long college day down to the games with a ranked team.
LEAGUES = [
    {"key": "wvb", "sport": "volleyball", "folder": "volleyball/", "name": "College volleyball", "label": "Volleyball", "score": "sets",
     "game": "#/match/", "ranked_only": True, "unit": "matches"},
    {"key": "lovb", "sport": "volleyball", "folder": "volleyball/lovb/", "name": "LOVB", "label": "Volleyball", "score": "sets",
     "game": "#/match/", "ranked_only": False, "unit": "matches"},
    {"key": "mlv", "sport": "volleyball", "folder": "volleyball/mlv/", "name": "MLV", "label": "Volleyball", "score": "sets",
     "game": "#/match/", "ranked_only": False, "unit": "matches"},
    {"key": "nhl", "sport": "hockey", "folder": "hockey/", "name": "NHL", "label": "Hockey", "score": "score",
     "game": "#/game/", "ranked_only": False, "unit": "games"},
    {"key": "nfl", "sport": "football", "folder": "football/nfl/", "name": "NFL", "label": "Football", "score": "score",
     "game": "#/game/", "ranked_only": False, "unit": "games"},
    {"key": "cfb", "sport": "football", "folder": "football/", "name": "College football", "label": "Football", "score": "score",
     "game": "#/game/", "ranked_only": True, "unit": "games"},
    {"key": "nba", "sport": "basketball", "folder": "basketball/nba/", "name": "NBA", "label": "Basketball", "score": "score",
     "game": "#/game/", "ranked_only": False, "unit": "games"},
    {"key": "cbb", "sport": "basketball", "folder": "basketball/", "name": "College basketball", "label": "Basketball", "score": "score",
     "game": "#/game/", "ranked_only": True, "unit": "games"},
    {"key": "mlb", "sport": "baseball", "folder": "baseball/", "name": "MLB", "label": "Baseball", "score": "score",
     "game": "#/game/", "ranked_only": False, "unit": "games"},
]
DAYS_BACK, DAYS_AHEAD = 2, 10        # the front page is given this many days either side of today
MARK = "<!-- sports bar -->"


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}] {msg}", flush=True)


def stamp(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def bar(current: str, up: str, ready: dict) -> str:
    """The strip across the top of every page: the site's name and one tab for each sport
    that has pages. `up` is the way from this page back to the front page ("../" or "../../");
    `ready` is {sport: the page its tab opens} for the sports that have pages."""
    tabs = "".join(
        f'<a href="{up}{ready[s["key"]]}"' + (' aria-current="page"' if s["key"] == current else "") + f'>{s["name"]}</a>'
        for s in SPORTS if s["key"] in ready)
    return (f'{MARK}<nav class="sports" aria-label="Sports"><div class="wrap sports-row">'
            f'<a class="sports-home" href="{up}">GOAT Sports</a>{tabs}</div></nav>')


def add_bar(page: Path, current: str, up: str, css: str, ready: dict) -> bool:
    """Write the bar into one page, in place of the one already there if it has one.
    Returns whether the page changed."""
    before = html = page.read_text(encoding="utf-8")
    assert "</head>" in html and "<body>" in html, f"{page} is not a page this step knows how to add the bar to"
    link = f'<link rel="stylesheet" href="{up}sports.css?v={css}">'
    html = re.sub(r'<link rel="stylesheet" href="[^"]*sports\.css[^"]*">\n?', "", html)
    html = html.replace("</head>", link + "\n</head>", 1)
    html = re.sub(re.escape(MARK) + r"<nav class=\"sports\".*?</nav>\n?", "", html, flags=re.S)
    skip = re.search(r'<a class="skip"[^>]*>.*?</a>\n?', html, re.S)       # keep "Skip to the games" first
    at = skip.end() if skip else html.index("<body>") + len("<body>\n")
    html = html[:at] + bar(current, up, ready) + "\n" + html[at:]
    if html != before:
        page.write_text(html, encoding="utf-8")
    return html != before


def front_games(site: Path, today: dt.date) -> list[dict]:
    """Each league's games around today, cut down to what the front page shows."""
    lo, hi = (today - dt.timedelta(days=DAYS_BACK)).isoformat(), (today + dt.timedelta(days=DAYS_AHEAD)).isoformat()
    out = []
    for lg in LEAGUES:
        path = site / lg["folder"] / "data.json"
        entry = {"key": lg["key"], "sport": lg["sport"], "name": lg["name"], "label": lg["label"], "href": lg["folder"],
                 "game": lg["folder"] + lg["game"], "unit": lg["unit"], "ranked_only": lg["ranked_only"], "games": [], "ready": False}
        out.append(entry)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except ValueError:
            continue
        entry.update(ready=True, updated=data.get("updated"), logo=data.get("logo") or None, logos=data.get("logos") or None,
                     abbr=data.get("abbr") or None, poll=(data.get("poll") or {}).get("name"))
        games = data.get("games") or []
        numbered = data.get("numbered", True)         # False before a season's first poll or first game: no numbers to show
        if lg["ranked_only"] and data.get("no_poll"):
            entry["ranked_only"] = False              # no top 25 yet, so nothing to narrow the day down to
        dates = sorted(g["date"] for g in games if g.get("date"))
        entry["first"], entry["last"] = (dates[0], dates[-1]) if dates else (None, None)
        entry["next"] = next((d for d in dates if d > hi), None)        # when the list is empty: the next day with a game
        for g in games:
            if not (lo <= g.get("date", "") <= hi):
                continue
            if entry["ranked_only"] and not (g["away"].get("rank") or g["home"].get("rank")):
                continue

            def side(s):
                return [s.get("id"), s.get("name"), s.get("rank") if numbered else None, s.get(lg["score"])]

            entry["games"].append({"id": g["id"], "date": g["date"], "start": g.get("start"), "state": g.get("state"),
                                   "note": g.get("note") or "", "away": side(g["away"]), "home": side(g["home"]),
                                   "p": g.get("p"), "tv": (g.get("tv") or g.get("watch") or [])[:2]})
        entry["games"].sort(key=lambda g: (g["date"], g["start"] or 0, g["id"]))
    return out


def main(built_dir: str, site_dir: str) -> int:
    built, site = Path(built_dir), Path(site_dir)
    site.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    fresh = []
    for s in SPORTS:
        src = built / s["key"]
        if (src / "index.html").exists() and (src / "data.json").exists():
            dest = site / s["key"]
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            fresh.append(s["key"])
    # the front page and the bar's stylesheet
    for f in HOME_SRC.iterdir():
        if f.is_file():
            shutil.copy(f, site / f.name)
    css = stamp(site / "sports.css")
    page = (site / "index.html").read_text(encoding="utf-8")
    for name in ("home.js", "home.css", "sports.css"):
        assert f'"{name}"' in page, f"home/index.html no longer refers to {name}"
        page = page.replace(f'"{name}"', f'"{name}?v={stamp(site / name)}"')
    (site / "index.html").write_text(page, encoding="utf-8")
    # where each sport's tab goes: its pro league's page if that has been built, its first page otherwise
    ready = {s["key"]: s["key"] + "/" + (s.get("home", "") if (site / s["key"] / s.get("home", "") / "index.html").exists() else "")
             for s in SPORTS if (site / s["key"] / "index.html").exists()}
    front = (site / "index.html").read_text(encoding="utf-8")
    front = re.sub(r'<nav class="sports".*?</nav>', bar("", "", ready).replace(MARK, "").replace(
        '<a class="sports-home" href=""', '<a class="sports-home" href="./" aria-current="page"'), front, count=1, flags=re.S)
    (site / "index.html").write_text(front, encoding="utf-8")
    barred = 0
    for s in SPORTS:
        for sub in s["pages"]:
            p = site / s["key"] / sub / "index.html"
            if p.exists():
                barred += add_bar(p, s["key"], "../" * (1 + sub.count("/")), css, ready)
    leagues = front_games(site, now.date())
    (site / "home.json").write_text(json.dumps({
        "updated": now.isoformat(timespec="seconds"),
        "sports": [{"key": s["key"], "name": s["name"], "href": ready.get(s["key"], s["key"] + "/"), "ready": (site / s["key"] / "index.html").exists()} for s in SPORTS],
        "leagues": leagues}, separators=(",", ":")))
    (site / ".nojekyll").write_text("")
    log(f"assembled: rebuilt {fresh or 'no sport'}; the bar was written into {barred} pages; front page lists "
        + ", ".join(f"{len(e['games'])} {e['name']}" for e in leagues))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

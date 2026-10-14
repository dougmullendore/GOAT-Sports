"""Power rankings from the big sports sites, for the pro leagues' Polls & Rankings tab.

Usage:  python -m tools.power_rankings <site_dir>

ESPN's power rankings are already read by each sport (they count in the GOAT ranking). This
reads the others: CBS Sports, FOX Sports and the league's own site, wherever they publish one.
Only the order is taken: each team's place, matched to the league's teams by name. The result
goes to <site_dir>/power/<league>.json, which the pages read.

The sites are read at most every REFRESH_HOURS (the site is published far more often than
that, every few minutes while games are on). A source that cannot be read keeps the copy read
last time; one older than MAX_AGE_DAYS is dropped, so a summer's rankings do not stand in for
the new season's. Anything going wrong here never stops the site being published.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

REFRESH_HOURS = 6
RETRY_HOURS = 1            # a league some of whose sites could not be read last time is tried again sooner
MAX_AGE_DAYS = 45
USER_AGENT = "Mozilla/5.0 (compatible; goat-sports-site/2.0; +https://github.com/dougmullendore/GOAT-Sports)"

# league: (its folder on the site, the sources to read)
LEAGUES = {
    "nfl": ("football/nfl", ["cbs", "fox", "nfl.com"]),
    "nba": ("basketball/nba", ["cbs", "fox", "nbc", "br", "yahoo", "clutch"]),      # NBA.com turns away automated readers
    "mlb": ("baseball", ["cbs", "fox"]),
    "nhl": ("hockey", ["cbs", "fox", "nhl.com"]),
    "cfb": ("football", ["espn", "cbs", "fox"]),
    "cbb": ("basketball", ["espn", "cbs", "fox"]),      # the same three sites as college football
}
LABELS = {"espn": "ESPN", "cbs": "CBS Sports", "fox": "FOX Sports", "nfl.com": "NFL.com", "nhl.com": "NHL.com",
          "nbc": "NBC Sports", "br": "Bleacher Report", "yahoo": "Yahoo Sports", "clutch": "ClutchPoints"}
# Rankings from sites whose newest one cannot be found on a page of theirs: this season's preseason
# rankings, read as given. Like every ranking they drop out once they are more than MAX_AGE_DAYS old.
FIXED = {
    "nba": {"br": "https://bleacherreport.com/articles/25504380-nba-power-rankings-entering-2026-preseason",
            "yahoo": "https://sports.yahoo.com/articles/nba-power-rankings-entering-2026-133600114.html",
            "clutch": "https://clutchpoints.com/nba/nba-stories/clutchpoints-2026-27-nba-power-rankings-biggest-question-all-30-teams-training-camp"},
}


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}] power rankings: {msg}", flush=True)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# ---------------------------------------------------------------- reading a page --
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", re.sub(r"['’]", "", s or "")).encode("ascii", "ignore").decode().lower()     # "St. John's" is "st johns"
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def text_of(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " \n ", page)
    return norm(html.unescape(page))


def order(page: str, teams: list[tuple[str, str, str]], lead: str = "") -> list[list]:
    """The teams of a ranking, as [[place, team id], ...] in order of place.

    Every "<number> <team name>" in the page's text is a candidate (`lead` is a word that must
    come before the number, such as "rank"). The ranking is the longest run of candidates whose
    numbers count 1, 2, 3... (or down from the last place, for a list written from the bottom)
    with no team twice. Scoreboards and links elsewhere on the page do not make such a run."""
    text = text_of(page)
    names = []
    for tid, *called in teams:                          # (id, full name, nickname, any other names a site uses)
        for n in {norm(c) for c in called}:
            if n:
                names.append((n, tid))
    names.sort(key=lambda x: -len(x[0]))
    who = dict(names)
    alt = "|".join(re.escape(n) for n, _ in names)
    between = r"(?:[a-z0-9]+ ){0,5}?" if lead else r"(?:[a-z]+ ){0,4}?"
    pat = (lead + " " if lead else "") + r"(?<![0-9])([0-9]{1,2}) " + between + r"(" + alt + r")(?![a-z0-9])"
    cands = [(int(m.group(1)), who[m.group(2)]) for m in re.finditer(pat, text)]
    best: list = []
    for start, (first, _) in enumerate(cands):
        for step in (1, -1):
            if (step == 1 and first != 1) or (step == -1 and first < 10):
                continue
            got, used, want = [], set(), first
            for place, tid in cands[start:]:
                if place == want and tid not in used:
                    got.append([place, tid]); used.add(tid); want += step
                    if want == 0:
                        break
            if len(got) > len(best):
                best = got
    return sorted(best)


def order_list(page: str, teams: list[tuple[str, ...]]) -> list[list]:
    """A ranking written as a numbered list (<ol>), its numbers left to the list itself: [[place, team id], ...]
    from the list whose items most often begin with a team's name."""
    names = sorted({(norm(c), tid) for tid, *called in teams for c in called if norm(c)}, key=lambda x: -len(x[0]))
    best: list = []
    for ol in re.findall(r"(?is)<ol[^>]*>(.*?)</ol>", page):
        got, used = [], set()
        for n, li in enumerate(re.findall(r"(?is)<li[^>]*>(.*?)</li>", ol), 1):
            text = text_of(li)
            tid = next((t for name, t in names if text == name or text.startswith(name + " ")), None)
            if tid and tid not in used:
                got.append([n, tid]); used.add(tid)
        if len(got) > len(best):
            best = got
    return best


def published(page: str) -> str | None:
    for pat in (r'"datePublished"\s*:\s*"([^"]+)"', r'article:published_time"\s+content="([^"]+)"', r'<time[^>]*datetime="([^"]+)"'):
        m = re.search(pat, page)
        if m:
            return m.group(1)
    return None


def headline(page: str) -> str:
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', page) or re.search(r"<title>([^<]+)", page)
    return html.unescape(m.group(1)).split(" | ")[0].strip() if m else ""


def when(stamp: str | None) -> dt.datetime | None:
    if not stamp:
        return None
    s = stamp.strip().replace(" UTC", "+00:00").replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S%z"):
        try:
            d = dt.datetime.fromisoformat(s) if fmt is None else dt.datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- where each site keeps its ranking --
# college: where each site's newest ranking is linked from, and how its address looks. A site that
# keeps several rankings stories on one page (FOX's basketball) has the newest one read.
COLLEGE = {
    "cfb": {"cbs": ("https://www.cbssports.com", "/college-football/", r'href="(/college-football/news/college-football-power-rankings[^"]*)"'),
            "fox": ("https://www.foxsports.com", "/stories/college-football", r'href="(/stories/college-football/(?:college-football-)?rankings-week-\d+[^"]*)"')},
    "cbb": {"cbs": ("https://www.cbssports.com", "/college-basketball/", r'href="(/college-basketball/news/college-basketball-rankings-[^"]*top-25-and-1[^"]*)"'),
            "fox": ("https://www.foxsports.com", "/stories/college-basketball", r'href="(/stories/college-basketball/(?:mens-)?college-basketball-rankings-[^"]*)"')},
}


# ESPN's college rankings are found with ESPN's article search and read from its article API (www.espn.com's
# pages turn the publish servers away; its APIs do not): what to search for, where the sport's stories live,
# and what a ranking's headline says. Rankings of something else (freshmen, recruits) are passed over.
ESPN_SEARCH = "https://site.web.api.espn.com/apis/search/v2?limit=20&type=article&query="
ESPN_STORY = "https://content.core.api.espn.com/v1/sports/news/{id}"
ESPN_COLLEGE = {"cfb": ("college football power rankings", "/college-football/story/", r"power rankings"),
                "cbb": ("men's college basketball top 25 rankings", "/mens-college-basketball/story/", r"power rankings|top 25 rankings")}
NOT_A_RANKING = re.compile(r"freshm|recruit|player|prospect|transfer|fantasy|draft|coach", re.I)


def espn_college(lg: str) -> tuple[str, str] | None:
    query, where, said = ESPN_COLLEGE[lg]
    found = {}

    def walk(node):
        if isinstance(node, dict):
            name = str(node.get("displayName") or node.get("headline") or "")
            link = node.get("link")
            url = str((link.get("web") if isinstance(link, dict) else link) or "")
            m = re.search(r"/id/(\d+)", url)
            if m and where in url and re.search(said, name, re.I) and not NOT_A_RANKING.search(name):
                found[m.group(1)] = (str(node.get("date") or node.get("published") or ""), m.group(1), name, url)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(json.loads(fetch(ESPN_SEARCH + urllib.parse.quote(query))))
    for date, sid, name, url in sorted(found.values(), reverse=True)[:3]:
        story = ((json.loads(fetch(ESPN_STORY.format(id=sid))).get("headlines") or [{}])[0]).get("story") or ""
        if story:      # the article's own text, with its headline and date where read_source looks for them
            return url, f'<meta property="og:title" content="{html.escape(name)}"><time datetime="{date}"></time>' + story
    return None


def find_college(lg: str, source: str) -> tuple[str, str] | None:
    """A college league's ranking from one site: the newest of those linked from its front page for the sport."""
    if source == "espn":
        return espn_college(lg)
    if source not in COLLEGE[lg]:
        raise ValueError(source)
    site, hub, pat = COLLEGE[lg][source]
    paths = list(dict.fromkeys(re.findall(pat, fetch(site + hub))))
    if not paths:
        return None
    if len(paths) == 1:
        return site + paths[0], fetch(site + paths[0])
    week = [(int(m.group(1)), path) for path in paths for m in [re.search(r"week-(\d+)", path)] if m]
    if len(week) == len(paths):                          # numbered by week: the highest
        url = site + max(week)[1]
        return url, fetch(url)
    newest = None                                        # otherwise the one published last
    for path in paths[:6]:
        page = fetch(site + path)
        stamp = when(published(page))
        if stamp and (newest is None or stamp > newest[0]):
            newest = (stamp, site + path, page)
    return (newest[1], newest[2]) if newest else None


def find_article(lg: str, source: str) -> tuple[str, str] | None:
    """(the ranking page's address, its contents), or None when the site has none to read."""
    if lg in COLLEGE:
        return find_college(lg, source)
    if source in FIXED.get(lg, {}):
        url = FIXED[lg][source]
        return url, fetch(url)
    if source == "nbc":                                   # the league's news page links the newest one
        hub = fetch(f"https://www.nbcsports.com/{lg}/news")
        m = re.search(r'href="((?:https://www\.nbcsports\.com)?/' + lg + r'/news/' + lg + r'-power-rankings[^"]*)"', hub)
        if not m:
            return None
        url = urllib.parse.urljoin("https://www.nbcsports.com/", m.group(1))
        return url, fetch(url)
    if source == "cbs":
        url = f"https://www.cbssports.com/{lg}/powerrankings/"
        return url, fetch(url)
    if source == "fox":                                   # the league's front page links the newest one
        hub = fetch(f"https://www.foxsports.com/{lg}")
        m = re.search(r'href="(/stories/' + lg + r'/[^"]*power-rankings[^"]*)"', hub)
        if not m:
            return None
        url = "https://www.foxsports.com" + m.group(1)
        return url, fetch(url)
    if source == "nfl.com":
        news = fetch("https://www.nfl.com/news/")
        m = re.search(r'href="((?:https://www\.nfl\.com)?/news/nfl-power-rankings-[^"]+)"', news)
        if not m:
            return None
        url = urllib.parse.urljoin("https://www.nfl.com/", m.group(1))
        return url, fetch(url)
    if source == "nhl.com":                               # the Super 16: the top sixteen, dated in the address
        topic = fetch("https://www.nhl.com/news/topic/super-16")
        found = []
        for path in set(re.findall(r'href="(/news/(?:topic/[a-z0-9-]+/)?super-16-nhl-power-rankings-([a-z]+-\d{1,2}-\d{4}))"', topic)):
            try:
                found.append((dt.datetime.strptime(path[1], "%B-%d-%Y"), path[0]))
            except ValueError:
                pass
        if not found:
            return None
        url = "https://www.nhl.com" + max(found)[1]
        return url, fetch(url)
    raise ValueError(source)


def league_teams(folder: Path) -> list[tuple[str, str, str]]:
    """(id, full name, nickname) for each of a league's teams, from its data.json."""
    data = json.loads((folder / "data.json").read_text(encoding="utf-8"))
    out = []
    for t in data.get("standings") or data.get("teams") or []:
        nick = t.get("short") or t.get("name") or ""
        full = (t.get("place", "") + " " + nick).strip() if t.get("place") else t.get("name", "")
        out.append((str(t["id"]), full, nick))
    if not out:                                           # college football: [id, name, conference, records] for each FBS team
        out = [(str(t[0]), t[1], t[1], *college_names(t[1])) for t in data.get("fbs") or []]
    return out


# the shorter names the sites write for some college teams
COLLEGE_NAMES = {"Mississippi State": ["Miss State"], "Miami": ["Miami (FL)", "Miami FL", "Miami (Fla.)"], "Miami (OH)": ["Miami OH"],
                 "Southern Miss": ["Southern Mississippi"], "UConn": ["Connecticut"], "UMass": ["Massachusetts"]}


def college_names(name: str) -> list[str]:
    more = list(COLLEGE_NAMES.get(name, []))
    if name.endswith(" State"):                          # "Michigan St"
        more.append(name[:-len("State")] + "St")
    return more


def read_source(lg: str, source: str, teams, now: dt.datetime) -> dict | None:
    got = find_article(lg, source)
    if not got:
        return None
    url, page = got
    ranks = order(page, teams, "rank" if source == "nfl.com" else "")
    if len(ranks) < min(16, len(teams)):                 # a numbered list instead, its numbers left to the list
        ranks = max(ranks, order_list(page, teams), key=len)
    if len(ranks) < min(16, len(teams)):
        raise RuntimeError(f"only {len(ranks)} teams could be read")
    stamp = when(published(page))
    return {"key": source, "label": LABELS[source], "headline": headline(page), "url": url,
            "published": stamp.isoformat(timespec="seconds") if stamp else None, "read": now.isoformat(timespec="seconds"),
            "teams": ranks}


def main(site_dir: str, force: bool = False) -> int:
    site = Path(site_dir)
    out_dir = site / "power"
    out_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    for lg, (folder, sources) in LEAGUES.items():
        if not (site / folder / "data.json").exists():
            continue
        path = out_dir / f"{lg}.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        last = when(old.get("read"))
        short = any(not str(v).startswith("read") for v in (old.get("tried") or {}).values()) or set(old.get("tried") or {}) != set(sources)
        wait = dt.timedelta(hours=RETRY_HOURS if short else REFRESH_HOURS)
        if not force and last and now - last < wait:
            continue
        teams = league_teams(site / folder)
        kept = {s["key"]: s for s in old.get("sources", [])}
        result, tried = [], {}
        for source in sources:
            try:
                got = read_source(lg, source, teams, now)
                if got:
                    kept[source] = got
                    tried[source] = f"read: {len(got['teams'])} teams"
                    log(f"{lg} {source}: {len(got['teams'])} teams, {got['published']}")
                else:
                    tried[source] = "none published"
                    log(f"{lg} {source}: none published")
            except Exception as e:  # a site down or redesigned: the copy read last time stays
                tried[source] = f"not read: {e!r}"[:200]
                log(f"{lg} {source}: not read ({e!r})"[:200])
            s = kept.get(source)
            age = when((s or {}).get("published")) or when((s or {}).get("read"))
            if s and age and now - age <= dt.timedelta(days=MAX_AGE_DAYS):
                result.append(s)
        path.write_text(json.dumps({"read": now.isoformat(timespec="seconds"), "sources": result, "tried": tried}, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1], "--force" in sys.argv))
    except Exception as e:  # never stops the site being published
        log(f"not updated ({e!r})")
        sys.exit(0)

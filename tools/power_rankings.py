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
MAX_AGE_DAYS = 45
USER_AGENT = "Mozilla/5.0 (compatible; goat-sports-site/2.0; +https://github.com/dougmullendore/GOAT-Sports)"

# league: (its folder on the site, the sources to read)
LEAGUES = {
    "nfl": ("football/nfl", ["cbs", "fox", "nfl.com"]),
    "nba": ("basketball/nba", ["cbs", "fox"]),          # NBA.com turns away automated readers
    "mlb": ("baseball", ["cbs", "fox"]),
    "nhl": ("hockey", ["cbs", "fox", "nhl.com"]),
}
LABELS = {"cbs": "CBS Sports", "fox": "FOX Sports", "nfl.com": "NFL.com", "nhl.com": "NHL.com"}


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%S}] power rankings: {msg}", flush=True)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# ---------------------------------------------------------------- reading a page --
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
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
    for tid, full, nick in teams:
        for n in {norm(full), norm(nick)}:
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
def find_article(lg: str, source: str) -> tuple[str, str] | None:
    """(the ranking page's address, its contents), or None when the site has none to read."""
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
    return out


def read_source(lg: str, source: str, teams, now: dt.datetime) -> dict | None:
    got = find_article(lg, source)
    if not got:
        return None
    url, page = got
    ranks = order(page, teams, "rank" if source == "nfl.com" else "")
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
        if not force and last and now - last < dt.timedelta(hours=REFRESH_HOURS):
            continue
        teams = league_teams(site / folder)
        kept = {s["key"]: s for s in old.get("sources", [])}
        result = []
        for source in sources:
            try:
                got = read_source(lg, source, teams, now)
                if got:
                    kept[source] = got
                    log(f"{lg} {source}: {len(got['teams'])} teams, {got['published']}")
                else:
                    log(f"{lg} {source}: none published")
            except Exception as e:  # a site down or redesigned: the copy read last time stays
                log(f"{lg} {source}: not read ({e!r})"[:200])
            s = kept.get(source)
            age = when((s or {}).get("published")) or when((s or {}).get("read"))
            if s and age and now - age <= dt.timedelta(days=MAX_AGE_DAYS):
                result.append(s)
        path.write_text(json.dumps({"read": now.isoformat(timespec="seconds"), "sources": result}, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1], "--force" in sys.argv))
    except Exception as e:  # never stops the site being published
        log(f"not updated ({e!r})")
        sys.exit(0)

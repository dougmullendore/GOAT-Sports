"""ESPN's power rankings: its writers' own order of a pro league's teams, published as an
article every week or so. The GOAT ranking uses the newest one the way a college site uses
the national poll.

ESPN's public search lists the articles; the newest whose headline says "Power Rankings" and
which ranks every team in the league exactly once is the one used. Only the order is taken
from it. It is looked for on every full update and kept in power.json; when none can be
read, the one stored stays in use, and with none stored the league's standings stand in.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from pathlib import Path

from . import config, web

SEARCH = "https://site.web.api.espn.com/apis/search/v2?limit=20&type=article&query="
STORY = "https://content.core.api.espn.com/v1/sports/news/{id}"
# articles that are called power rankings but rank something else
NOT_THIS = re.compile(r"future|survivor|fantasy|draft|prospect|rookie|quarterback|\bqb\b|uniform|mascot|all-time", re.I)
# one team's heading: <h2>7. <a href=".../nfl/team/_/name/sf/san-francisco-49ers">San Francisco 49ers</a> (4-0)</h2>
HEADING = re.compile(r"<h2>\s*(\d{1,2})\.\s*<a[^>]*href=\"[^\"]*/team/_/name/([a-z0-9]+)/[^\"]*\"[^>]*>([^<]+)</a>", re.I)
TRIES = 4            # how many of the newest articles are opened before giving up


def candidates(doc: dict, league: str) -> list[dict]:
    """The power-ranking articles in a search result, newest first: [{"id", "headline", "published", "url"}]."""
    found = {}

    def walk(node):
        if isinstance(node, dict):
            name = node.get("displayName") or node.get("headline") or node.get("title") or ""
            link = node.get("link")
            url = (link.get("web") if isinstance(link, dict) else link) or ""
            m = re.search(r"/id/(\d+)", str(url))
            if isinstance(name, str) and m and re.search(r"power rankings", name, re.I) and not NOT_THIS.search(name) \
                    and f"/{league}/story/" in str(url):
                found[m.group(1)] = {"id": m.group(1), "headline": name.strip(), "published": str(node.get("date") or node.get("published") or ""), "url": str(url)}
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return sorted(found.values(), key=lambda a: a["published"], reverse=True)


def parse_story(doc: dict) -> list[tuple[int, str, str]]:
    """[(rank, ESPN's short name for the team, the team's name)] from an article, in the order written."""
    story = (((doc or {}).get("headlines") or [{}])[0]).get("story") or ""
    return [(int(n), abbr.upper(), name.strip()) for n, abbr, name in HEADING.findall(story)]


def _key(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def match(rows: list[tuple[int, str, str]], teams: dict) -> dict | None:
    """{team id: rank} if the article ranks every team in `teams` exactly once, 1 to N; otherwise None.
    `teams` is {team id: [the names it may go by: short name first, then its full name and nickname]}."""
    by_abbr, by_name = {}, {}
    for tid, names in teams.items():
        by_abbr[str(names[0]).upper()] = tid
        for n in names[1:]:
            if n:
                by_name[_key(n)] = tid
    out = {}
    for rank, abbr, name in rows:
        tid = by_abbr.get(config.POWER_ABBR.get(abbr, abbr)) or by_name.get(_key(name))
        if tid is None or tid in out:
            return None
        out[tid] = rank
    if set(out) != set(teams) or sorted(out.values()) != list(range(1, len(teams) + 1)):
        return None
    return out


def update(state: Path, now: dt.datetime, teams: dict, log=print) -> dict:
    """Look for a newer power ranking than the one stored. Never fails the run."""
    league = getattr(config, "POWER", None)
    path = state / "power.json"
    stored = json.loads(path.read_text()) if path.exists() else {}
    if not league or not teams:
        return {"read": False}
    try:
        listed = candidates(json.loads(web.get_bytes(SEARCH + urllib.parse.quote(f"{league} power rankings"))), league)
        for article in listed[:TRIES]:
            if stored.get("id") == article["id"] and set(stored.get("ranks") or {}) == set(teams):
                return {"read": False, "newest": stored.get("headline"), "published": stored.get("published")}
            ranks = match(parse_story(json.loads(web.get_bytes(STORY.format(id=article["id"])))), teams)
            if ranks:
                path.write_text(json.dumps({**article, "read": now.isoformat(timespec="seconds"), "ranks": ranks}, separators=(",", ":")))
                log(f"power ranking: {article['headline']} ({article['published'][:10]})")
                return {"read": True, "newest": article["headline"], "published": article["published"]}
            log(f"power ranking: could not read every team's place from \"{article['headline']}\"; trying an older one")
        raise RuntimeError(f"none of the {len(listed)} articles found could be used")
    except Exception as e:
        log(f"power ranking: not updated ({e!r}); keeping {'the one stored' if stored.get('ranks') else 'the standings'}"[:220])
        return {"read": False, "failed": True, "newest": stored.get("headline")}


def stored(state: Path, teams) -> dict:
    """What is stored, if it still covers exactly these teams: {"ranks": {team: rank}, "headline", "published", "url"}; else {}."""
    path = state / "power.json"
    doc = json.loads(path.read_text()) if path.exists() else {}
    return doc if doc.get("ranks") and set(doc["ranks"]) == {str(t) for t in teams} else {}

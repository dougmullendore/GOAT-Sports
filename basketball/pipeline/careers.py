"""Career stats: each player's seasons, as ESPN lists them.

ESPN keeps a page of season-by-season numbers for every player, with a line
for each school he has played for, so a transfer's earlier seasons come with
him. A player's page is read once and kept in <state>/careers.json, and read
again after his team's next game, at most CAREERS_PER_RUN players a run, the
ranked teams' players first. Until a player's page has been read his card
shows this season only.
"""
from __future__ import annotations

from . import config, espn, web

VERSION = 2
SETTLE_HOURS = 5         # a page read sooner than this after kickoff may not have that game in it yet


def update(stored: dict, wanted: list[tuple[str, int]], now: int, log, limit: int | None = None) -> dict:
    """Read some more players' careers. `wanted` is [(player id, when his team's
    latest game kicked off)], most wanted first; times are seconds since 1970.
    Changes `stored`: {"v", "players": {id: {"t": when it was read, "c": his seasons}}}"""
    if stored.get("v") != VERSION:
        stored.clear()
        stored.update(v=VERSION, players={})
    limit = config.CAREERS_PER_RUN if limit is None else limit
    keep = {pid for pid, _ in wanted}
    stored["players"] = {k: v for k, v in stored["players"].items() if k in keep}
    def stale(pid, played):
        return pid not in stored["players"] or stored["players"][pid]["t"] < played + SETTLE_HOURS * 3600

    todo = [pid for pid, played in wanted if stale(pid, played)][:limit]
    urls = {config.CAREER.format(player=pid): pid for pid in todo}
    read = failed = 0
    for url, doc, err in web.get_many(list(urls), tries=2):
        pid = urls[url]
        if err is not None:
            failed += 1
            # a player ESPN has no page for is not asked about again until his team's next game
            if "404" in repr(err):
                stored["players"][pid] = {"t": now, "c": (stored["players"].get(pid) or {}).get("c") or []}
            continue
        stored["players"][pid] = {"t": now, "c": espn.parse_career(doc)}
        read += 1
    left = sum(1 for pid, played in wanted if stale(pid, played))
    log(f"careers: {read} players read ({failed} failed); {len(stored['players'])} of {len(wanted)} kept, {left} still to read")
    return {"read": read, "failed": failed, "kept": len(stored["players"]), "wanted": len(wanted), "to_read": left}


def by_player(stored: dict) -> dict:
    return {pid: v["c"] for pid, v in (stored.get("players") or {}).items() if v.get("c")}

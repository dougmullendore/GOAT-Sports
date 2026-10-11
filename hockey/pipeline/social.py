"""Players' own social media pages, for their cards.

No sports feed lists them, so they come from Wikidata, the open database behind
Wikipedia, which records a player's Instagram, X and TikTok names next to his
ESPN or NHL id. It knows a little under half of today's players. The list is
read again once a week and kept in social.json; when it cannot be read the copy
already stored stays in use, and the update carries on either way.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from . import config

SPARQL = "https://query.wikidata.org/sparql?format=json&query="
# network: (Wikidata's property, what a name there may look like, the address of the page)
NETWORKS = {
    "instagram": ("P2003", r"[A-Za-z0-9._]{1,30}", "https://www.instagram.com/{}"),
    "twitter": ("P2002", r"[A-Za-z0-9_]{1,15}", "https://x.com/{}"),
    "tiktok": ("P7085", r"[A-Za-z0-9._]{2,24}", "https://www.tiktok.com/@{}"),
}
REFRESH_DAYS = 7
# Wikidata asks every program that reads it to say who it is.
USER_AGENT = "GOAT-Sports/1.0 (https://github.com/dougmullendore/GOAT-Sports; sports site data job)"


def fetch(url: str) -> bytes:
    if os.environ.get("FETCH_CACHE"):                  # the tests never go to the internet
        raise RuntimeError("not read while testing")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def query(prop: str) -> str:
    """Everyone with an id of this kind (ESPN's NFL id, say) and at least one of the names."""
    wanted = " ".join(f"OPTIONAL {{ ?p wdt:{p} ?{net} }}" for net, (p, *_) in NETWORKS.items())
    any_of = " || ".join(f"BOUND(?{net})" for net in NETWORKS)
    return f"SELECT ?id {' '.join('?' + n for n in NETWORKS)} WHERE {{ ?p wdt:{prop} ?id . {wanted} FILTER({any_of}) }}"


def parse(doc: dict) -> dict:
    """{player id: {"instagram": address, ...}} from Wikidata's answer. A name that does not
    look like one is left out; where a player has two, the first is kept."""
    out = {}
    for row in ((doc or {}).get("results") or {}).get("bindings") or []:
        pid = str((row.get("id") or {}).get("value") or "").strip()
        if not pid:
            continue
        for net, (_, shape, address) in NETWORKS.items():
            name = str((row.get(net) or {}).get("value") or "").strip().lstrip("@")
            if name and re.fullmatch(shape, name) and net not in out.get(pid, {}):
                out.setdefault(pid, {})[net] = address.format(name)
    return out


def update(state: Path, today: dt.date, log=print) -> dict:
    """Read the list if there is none stored or it is a week old. Never fails the run."""
    prop = getattr(config, "SOCIAL_IDS", None)
    path = state / "social.json"
    stored = json.loads(path.read_text()) if path.exists() else {}
    if not prop:
        return {"read": False, "players": 0}
    age = (today - dt.date.fromisoformat(stored["read"])).days if stored.get("read") else None
    if age is not None and age < REFRESH_DAYS and stored.get("ids") == prop:
        return {"read": False, "players": len(stored.get("players") or {}), "age_days": age}
    try:
        found = parse(json.loads(fetch(SPARQL + urllib.parse.quote(query(prop)))))
        if not found:
            raise RuntimeError("the list came back empty")
    except Exception as e:
        log(f"social links: could not be read ({e!r}); keeping the {len(stored.get('players') or {})} stored"[:220])
        return {"read": False, "players": len(stored.get("players") or {}), "failed": True}
    path.write_text(json.dumps({"read": today.isoformat(), "ids": prop, "players": found}, separators=(",", ":")))
    log(f"social links: {len(found):,} players have one on Wikidata")
    return {"read": True, "players": len(found)}


def add(state: Path, players: list[dict]) -> int:
    """Put each player's links on his card (bio.social), where they are known. Returns how many have some."""
    path = state / "social.json"
    known = (json.loads(path.read_text()).get("players") or {}) if path.exists() else {}
    n = 0
    for p in players:
        links = known.get(str(p.get("id")))
        if links:
            p["bio"] = {**(p.get("bio") or {}), "social": links}
            n += 1
    return n

import json, sys, os, gzip, urllib.request, urllib.parse, time, re
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
UA = "Mozilla/5.0 (compatible; goat-sports/1.0)"
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html, */*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()
def save(name, body):
    with gzip.open(os.path.join(out, name + ".gz"), "wb") as f: f.write(body[:4_000_000])
index = {}
def try_(name, url):
    t = time.time()
    try:
        st, body = get(url); save(name, body)
        try: doc = json.loads(body)
        except Exception: doc = None
        index[name] = {"url": url, "status": st, "bytes": len(body), "json": doc is not None, "top": list(doc.keys())[:12] if isinstance(doc, dict) else None}
        print(name, json.dumps(index[name])[:300]); return doc, body
    except Exception as e:
        index[name] = {"url": url, "error": repr(e)[:300]}; print(name, index[name]); return None, b""
LEAGUES = {"nfl": "football/nfl", "nba": "basketball/nba", "mlb": "baseball/mlb", "nhl": "hockey/nhl"}
found = {}
for lg, path in LEAGUES.items():
    hits = []
    doc, _ = try_(f"news_{lg}", f"https://site.api.espn.com/apis/site/v2/sports/{path}/news?limit=150")
    for a in (doc or {}).get("articles") or []:
        if re.search(r"power rank", a.get("headline") or "", re.I):
            hits.append({"src": "news", "id": a.get("id") or (a.get("dataSourceIdentifier")), "headline": a.get("headline"), "published": a.get("published"), "links": ((a.get("links") or {}).get("api") or {}), "web": ((a.get("links") or {}).get("web") or {}).get("href")})
    doc, _ = try_(f"search_{lg}", "https://site.web.api.espn.com/apis/search/v2?limit=20&type=article&query=" + urllib.parse.quote(f"{lg} power rankings"))
    def walk(o):
        if isinstance(o, dict):
            name = o.get("displayName") or o.get("headline") or o.get("title") or ""
            if isinstance(name, str) and re.search(r"power rank", name, re.I):
                hits.append({"src": "search", "id": o.get("id"), "headline": name, "published": o.get("date") or o.get("published"), "web": (o.get("link") or {}).get("web") if isinstance(o.get("link"), dict) else o.get("link")})
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(doc)
    doc, _ = try_(f"now_{lg}", f"https://now.core.api.espn.com/v1/sports/news?limit=100&sport={path.split('/')[0]}&league={lg}")
    for a in (doc or {}).get("headlines") or (doc or {}).get("feed") or []:
        if re.search(r"power rank", a.get("headline") or "", re.I):
            hits.append({"src": "now", "id": a.get("id"), "headline": a.get("headline"), "published": a.get("published"), "web": ((a.get("links") or {}).get("web") or {}).get("href")})
    found[lg] = hits
    print(lg, "HITS", json.dumps(hits)[:1500])
    seen = set()
    for h in hits[:6]:
        i = str(h.get("id") or "")
        m = re.search(r"/id/(\d+)", h.get("web") or "")
        i = i if i.isdigit() else (m.group(1) if m else "")
        if not i or i in seen: continue
        seen.add(i)
        try_(f"story_{lg}_{i}", f"https://content.core.api.espn.com/v1/sports/news/{i}")
        if len(seen) >= 2: break
    time.sleep(1)
# ESPN's own rating systems, in case the articles cannot be read
try_("fpi_nfl", "https://site.web.api.espn.com/apis/fitt/v3/sports/football/nfl/powerindex?region=us&lang=en&limit=50")
try_("bpi_nba", "https://site.web.api.espn.com/apis/fitt/v3/sports/basketball/nba/powerindex?region=us&lang=en&limit=50")
try_("pi_mlb", "https://site.web.api.espn.com/apis/fitt/v3/sports/baseball/mlb/powerindex?region=us&lang=en&limit=50")
try_("pi_nhl", "https://site.web.api.espn.com/apis/fitt/v3/sports/hockey/nhl/powerindex?region=us&lang=en&limit=50")
index["found"] = found
json.dump(index, open(os.path.join(out, "index.json"), "w"), indent=1)

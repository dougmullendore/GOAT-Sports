import json, sys, os, gzip, urllib.request, time
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; goat-sports/1.0)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()
index = {}
B = "https://site.api.espn.com/apis/site/v2/sports/basketball/"
tests = {
 "cbb_now": B + "mens-college-basketball/scoreboard?limit=400&groups=50",
 "cbb_jan": B + "mens-college-basketball/scoreboard?dates=20260115&limit=400&groups=50",
 "cbb_apr": B + "mens-college-basketball/scoreboard?dates=20260406&limit=400&groups=50",
 "nba_now": B + "nba/scoreboard?limit=400",
 "nba_jan": B + "nba/scoreboard?dates=20260115&limit=400",
 "nba_jun": B + "nba/scoreboard?dates=20260610&limit=400",
 "cbb_rank": B + "mens-college-basketball/rankings",
 "cbb_stand_2026": "https://site.api.espn.com/apis/v2/sports/basketball/mens-college-basketball/standings?season=2026&level=3",
 "nba_stand_2026": "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings?season=2026&level=3",
 "nba_stand_2026_t2": "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings?season=2026&seasontype=2&level=3",
}
for name, url in tests.items():
    try:
        body = get(url); doc = json.loads(body)
        with gzip.open(os.path.join(out, name + ".gz"), "wb") as f: f.write(body[:3_000_000])
        lg = (doc.get("leagues") or [{}])[0]
        info = {"season": lg.get("season"), "calStart": lg.get("calendarStartDate"), "calEnd": lg.get("calendarEndDate"), "cal_n": len(lg.get("calendar") or []), "cal_first": (lg.get("calendar") or [None])[0], "cal_last": (lg.get("calendar") or [None])[-1],
                "events": len(doc.get("events") or []), "ev_season": [((e.get("season") or {}).get("year"), (e.get("season") or {}).get("type")) for e in (doc.get("events") or [])[:2]]}
        if "rankings" in doc:
            info["rankings"] = [(r.get("name"), r.get("type"), (r.get("season") or {}), r.get("date"), r.get("headline"), (r.get("occurrence") or {})) for r in doc["rankings"][:3]]
        index[name] = info
    except Exception as e:
        index[name] = {"error": repr(e)[:300]}
    print(name, json.dumps(index[name])[:900])
json.dump(index, open(os.path.join(out, "index.json"), "w"), indent=1)

import json, sys, os, gzip, hashlib, urllib.request, urllib.parse, time
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
UA = "Mozilla/5.0 (compatible; goat-sports/1.0)"
def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, */*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.status, r.read()
def ncaa(sport, division, season, date=None, week=None):
    h = "7287cda610a9326931931080cb3a604828febe6fe3c9016a7e4a36db99efdb7c"
    ext = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": h}}, separators=(",", ":"))
    v = {"sportCode": sport, "division": division, "seasonYear": season}
    if date: v["contestDate"] = date
    if week is not None: v["week"] = week
    return "https://sdataprod.ncaa.com/?extensions=" + urllib.parse.quote(ext) + "&variables=" + urllib.parse.quote(json.dumps(v, separators=(",", ":")))
Y = "https://api-secure.sports.yahoo.com/v1/editorial/s/scoreboard?leagues={lg}&date={d}"
tests = {
 "yahoo_nba_oct20": Y.format(lg="nba", d="2026-10-20"),
 "yahoo_nba_mar01": Y.format(lg="nba", d="2026-03-01"),
 "yahoo_nba_today": Y.format(lg="nba", d="2026-10-11"),
 "yahoo_ncaaf": Y.format(lg="ncaaf", d="2026-10-10"),
 "yahoo_ncaab": Y.format(lg="ncaab", d="2026-03-14"),
 "yahoo_mlb": Y.format(lg="mlb", d="2026-09-26"),
 "yahoo_nhl": Y.format(lg="nhl", d="2026-10-10"),
 "nba_cdn_schedule_ref": "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
 "nba_data_today": "https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData/scoreboard/todaysScoreboard_00.json",
 "nhl_api_score": "https://api-web.nhle.com/v1/score/2026-10-10",
 "lovb_home": "https://www.lovb.com/",
 "mlv_home": "https://provolleyball.com/",
}
index = {}
for name, url in tests.items():
    t = time.time()
    try:
        status, body = get(url, {"Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"} if "nba" in url and "yahoo" not in url else None)
        kind = "json"
        try: doc = json.loads(body)
        except Exception: doc, kind = None, "not json"
        with gzip.open(os.path.join(out, name + ".gz"), "wb") as f: f.write(body[:3_000_000])
        top = list(doc.keys())[:12] if isinstance(doc, dict) else type(doc).__name__
        index[name] = {"url": url, "status": status, "bytes": len(body), "kind": kind, "top": top, "secs": round(time.time() - t, 2)}
    except Exception as e:
        index[name] = {"url": url, "error": repr(e)[:300], "secs": round(time.time() - t, 2)}
    print(name, json.dumps(index[name])[:400])
json.dump(index, open(os.path.join(out, "index.json"), "w"), indent=1)

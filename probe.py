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
tests = {
 "mlb_statsapi_today": "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=2026-10-11&hydrate=linescore,team",
 "mlb_statsapi_sep26": "https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=2026-09-26&hydrate=linescore,team",
 "nba_cdn_schedule": "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
 "nba_cdn_today": "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json",
 "nhl_espn_today": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?limit=100&dates=20261011",
 "nhl_espn_yday": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?limit=100&dates=20261010",
 "ncaa_mfb_date": ncaa("MFB", 11, 2026, date="2026/10/10"),
 "ncaa_mfb_week": ncaa("MFB", 11, 2026, week=7),
 "ncaa_mfb_week6": ncaa("MFB", 11, 2026, week=6),
 "ncaa_mbb_date": ncaa("MBB", 1, 2025, date="2026/03/14"),
 "ncaa_mbb_nov": ncaa("MBB", 1, 2026, date="2026/11/03"),
 "nfl_yahoo": "https://api-secure.sports.yahoo.com/v1/editorial/s/scoreboard?leagues=nfl&week=5&season=2026",
 "nfl_yahoo_date": "https://api-secure.sports.yahoo.com/v1/editorial/s/scoreboard?leagues=nfl&date=2026-10-11",
 "nfl_espn_cdn": "https://cdn.espn.com/core/nfl/scoreboard?xhr=1&limit=50",
 "nfl_espn_core": "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/weeks/5/events?limit=50",
 "nfl_tsdb_3": "https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d=2026-10-11&l=NFL",
 "nfl_tsdb_123": "https://www.thesportsdb.com/api/v1/json/123/eventsday.php?d=2026-10-11&l=NFL",
 "nfl_cbs": "https://www.cbssports.com/nfl/scoreboard/",
 "nfl_nflcom": "https://www.nfl.com/scores/",
 "nfl_fox": "https://api.foxsports.com/bifrost/v1/nfl/league/scores-segment/2026-5-1?apikey=jE7yBJVRNAwdDesMgTzTXUUSx1It41Fq",
 "lovb_site": "https://www.lovb.com/schedule",
 "mlv_site": "https://provolleyball.com/schedule",
 "wvb_espn_today": "https://site.api.espn.com/apis/site/v2/sports/volleyball/womens-college-volleyball/scoreboard?limit=500&dates=20261011",
 "cfb_espn_alt": "https://cdn.espn.com/core/college-football/scoreboard?xhr=1&limit=200&group=80",
 "mlb_espn_alt": "https://cdn.espn.com/core/mlb/scoreboard?xhr=1&limit=50",
}
index = {}
for name, url in tests.items():
    t = time.time()
    try:
        status, body = get(url)
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

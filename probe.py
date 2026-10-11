import json, subprocess, sys, os
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/dougmullendore/GOAT-Sports", "repo"], check=True)
sys.path.insert(0, "repo/volleyball")
from pipeline import web, config
res = {}
try:
    doc = json.loads(web.get_bytes(web.scoreboard_url(2026, "2026-10-11")))
    def find(o):
        if isinstance(o, dict):
            if str(o.get("contestId")) == "6624393": return o
            for v in o.values():
                r = find(v)
                if r: return r
        elif isinstance(o, list):
            for v in o:
                r = find(v)
                if r: return r
    res["ncaa"] = find(doc)
except Exception as e:
    res["ncaa_error"] = repr(e)
try:
    doc = json.loads(web.get_bytes(config.ESPN_SCOREBOARD + "20261011"))
    for e in doc.get("events", []):
        names = " ".join(c["team"].get("location", "") for c in e["competitions"][0]["competitors"])
        if str(e["id"]) == "401884234" or ("Illinois" in names and "Purdue" in names):
            c = e["competitions"][0]
            res.setdefault("espn", []).append({"id": e["id"], "date": e["date"], "status": e["status"], "teams": [(x["homeAway"], x["team"]["location"], x.get("score"), [l.get("value") for l in x.get("linescores", [])]) for x in c["competitors"]]})
except Exception as e:
    res["espn_error"] = repr(e)
json.dump(res, open(os.path.join(out, "illpur.json"), "w"), indent=1)
print(json.dumps(res, indent=1)[:3000])

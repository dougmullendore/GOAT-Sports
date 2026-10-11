import json, sys, os, gzip, urllib.request, urllib.parse, time
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
UA = "GOAT-Sports/1.0 (https://github.com/dougmullendore/GOAT-Sports; sports site data job)"
def get(url, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()
def save(name, body):
    with gzip.open(os.path.join(out, name + ".gz"), "wb") as f: f.write(body)
index = {"props": {}, "sets": {}}
# 1. which properties exist
found = {}
for term in ["ESPN", "NHL.com player", "MLB.com player", "NBA.com player", "NFL.com", "Instagram username", "X username", "TikTok username",
             "college football player", "college basketball player", "Pro Volleyball", "League One Volleyball", "volleyball player ID", "Facebook username", "Threads username", "YouTube channel ID"]:
    try:
        d = json.loads(get("https://www.wikidata.org/w/api.php?action=wbsearchentities&language=en&type=property&limit=50&format=json&search=" + urllib.parse.quote(term)))
        for x in d.get("search", []):
            found[x["id"]] = [x.get("label"), (x.get("description") or "")[:120]]
    except Exception as e:
        print("search failed", term, repr(e)[:200])
    time.sleep(1)
index["props"] = found
for k, v in sorted(found.items()): print(k, v)
# 2. for every id property that looks like a player id of ours: everyone with a social handle
want = [p for p, (label, _) in found.items() if label and any(w in label for w in ("ESPN", "NHL.com player", "MLB.com player", "NBA.com player", "volleyball", "Volleyball"))]
SOC = {"ig": "P2003", "x": "P2002", "tt": "P7085", "fb": "P2013", "th": "P11892", "yt": "P2397"}
for p in want:
    try:
        q = "SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE { ?p wdt:%s ?id }" % p
        n = json.loads(get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q)))["results"]["bindings"][0]["n"]["value"]
        time.sleep(2)
        opt = " ".join("OPTIONAL { ?p wdt:%s ?%s }" % (v, k) for k, v in SOC.items())
        q = "SELECT ?id %s WHERE { ?p wdt:%s ?id . %s FILTER(%s) }" % (" ".join("?" + k for k in SOC), p, opt, " || ".join("BOUND(?%s)" % k for k in SOC))
        body = get("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))
        rows = json.loads(body)["results"]["bindings"]
        slim = {}
        for r in rows:
            e = slim.setdefault(r["id"]["value"], {})
            for k in SOC:
                if k in r: e.setdefault(k, r[k]["value"])
        save("soc_" + p, json.dumps(slim, separators=(",", ":")).encode())
        index["sets"][p] = {"label": found[p][0], "people": int(n), "with_social": len(slim), "ig": sum(1 for e in slim.values() if "ig" in e), "x": sum(1 for e in slim.values() if "x" in e)}
    except Exception as e:
        index["sets"][p] = {"label": found[p][0], "error": repr(e)[:300]}
    print(p, json.dumps(index["sets"][p]))
    time.sleep(3)
json.dump(index, open(os.path.join(out, "index.json"), "w"), indent=1)

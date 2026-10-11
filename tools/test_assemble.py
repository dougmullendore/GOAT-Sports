"""Checks for tools/assemble.py. Run with:  python -m tools.test_assemble"""
import json
import sys
import tempfile
from pathlib import Path

from . import assemble

PAGE = '<!doctype html>\n<html>\n<head>\n<title>x</title>\n</head>\n<body>\n<a class="skip" href="#games">Skip to the games</a>\n<main></main>\n</body>\n</html>\n'


def sport(folder: Path, games: list, extra: dict | None = None) -> None:
    folder.mkdir(parents=True)
    (folder / "index.html").write_text(PAGE)
    (folder / "data.json").write_text(json.dumps({"updated": "2026-10-10T12:00:00+00:00", "logo": "https://example.org/{team}.svg",
                                                  "games": games, **(extra or {})}))


def game(i, date, rank=None, key="score"):
    return {"id": i, "date": date, "start": 1791669600, "state": "final", "note": "",
            "away": {"id": "a", "name": "Away", "rank": rank, key: 1}, "home": {"id": "h", "name": "Home", "rank": None, key: 3}}


def main() -> int:
    import datetime as dt
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        built, site = Path(tmp) / "built", Path(tmp) / "site"
        sport(built / "hockey", [game(1, today), game(2, "2020-01-01")])
        sport(built / "volleyball", [game(3, today, 5, "sets"), game(4, today, None, "sets")], {"poll": {"name": "AVCA coaches poll"}, "nr": {"h": 31}})
        sport(built / "volleyball" / "lovb", [])
        assert assemble.main(str(built), str(site)) == 0
        home = json.loads((site / "home.json").read_text())
        by = {l["key"]: l for l in home["leagues"]}
        assert [g["id"] for g in by["nhl"]["games"]] == [1]                    # only the days around today
        assert [g["id"] for g in by["wvb"]["games"]] == [3]                    # college: only games with a ranked team
        assert by["wvb"]["games"][0]["away"] == ["a", "Away", 5, 1] and by["wvb"]["poll"] == "AVCA coaches poll"
        assert by["wvb"]["games"][0]["home"][2] == 31                         # outside the poll: its GOAT number
        assert not by["cfb"]["ready"] and [s["key"] for s in home["sports"] if s["ready"]] == ["hockey", "volleyball"]
        hockey = (site / "hockey" / "index.html").read_text()
        assert hockey.count(assemble.MARK) == 1 and 'href="../volleyball/"' in hockey and "football" not in hockey
        assert hockey.index("Skip to the games") < hockey.index(assemble.MARK)
        assert 'href="../../hockey/"' in (site / "volleyball" / "lovb" / "index.html").read_text()
        front = (site / "index.html").read_text()
        assert 'href="football/"' not in front and "home.js?v=" in front
        # football arrives on a later run that rebuilds nothing else: every page gets its tab, the other sports' pages stay
        (built / "hockey" / "data.json").unlink()
        sport(Path(tmp) / "later" / "football", [game(9, today, 1)], {"poll": {"name": "AP Top 25"}})
        assert assemble.main(str(Path(tmp) / "later"), str(site)) == 0
        hockey = (site / "hockey" / "index.html").read_text()
        assert hockey.count(assemble.MARK) == 1 and hockey.count("sports.css") == 1 and 'href="../football/"' in hockey
        assert 'aria-current="page">Football' in (site / "football" / "index.html").read_text()
        later = {l["key"]: l for l in json.loads((site / "home.json").read_text())["leagues"]}
        assert [g["id"] for g in later["cfb"]["games"]] == [9] and not later["nfl"]["ready"]
        assert [l["sport"] for l in later.values()] == ["football"] * 2 + ["basketball"] * 2 + ["baseball", "hockey"] + ["volleyball"] * 3
        assert [s["key"] for s in assemble.SPORTS] == ["football", "basketball", "baseball", "hockey", "volleyball"]
        # basketball before its season: no poll, so the whole day is listed, and nobody has a number
        sport(Path(tmp) / "third" / "basketball", [game(11, today), game(12, today)], {"poll": {"name": "AP Top 25"}, "no_poll": True, "numbered": False})
        sport(Path(tmp) / "third" / "basketball" / "nba", [game(13, today, 4)], {"numbered": False})
        sport(Path(tmp) / "third" / "baseball", [game(14, today, 2)])
        assert assemble.main(str(Path(tmp) / "third"), str(site)) == 0
        third = {l["key"]: l for l in json.loads((site / "home.json").read_text())["leagues"]}
        assert [g["id"] for g in third["cbb"]["games"]] == [11, 12] and not third["cbb"]["ranked_only"]
        assert third["nba"]["games"][0]["away"][2] is None and third["mlb"]["games"][0]["away"][2] == 2
        nba = (site / "basketball" / "nba" / "index.html").read_text()
        assert 'href="../../baseball/"' in nba and nba.index("Football<") < nba.index("Basketball<") < nba.index("Baseball<") < nba.index("Hockey<") < nba.index("Volleyball<")
        assert 'aria-current="page">Baseball' in (site / "baseball" / "index.html").read_text()
        # the pro league comes first: a sport's tab opens it, and the front page lists it before the college one
        assert 'href="../../basketball/nba/"' in nba and 'href="../basketball/nba/"' in (site / "hockey" / "index.html").read_text()
        assert 'href="basketball/nba/"' in (site / "index.html").read_text()
        final = json.loads((site / "home.json").read_text())
        assert {s["key"]: s["href"] for s in final["sports"]} == {"volleyball": "volleyball/", "hockey": "hockey/", "football": "football/",
                                                                  "basketball": "basketball/nba/", "baseball": "baseball/"}       # football has no NFL pages here
        assert [l["key"] for l in final["leagues"]] == ["nfl", "cfb", "nba", "cbb", "mlb", "nhl", "wvb", "lovb", "mlv"]
        assert (site / "volleyball" / "data.json").exists()
    print("PASS tools.assemble")
    return 0


if __name__ == "__main__":
    sys.exit(main())

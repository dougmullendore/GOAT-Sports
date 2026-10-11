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
        sport(built / "volleyball", [game(3, today, 5, "sets"), game(4, today, None, "sets")], {"poll": {"name": "AVCA coaches poll"}})
        sport(built / "volleyball" / "lovb", [])
        assert assemble.main(str(built), str(site)) == 0
        home = json.loads((site / "home.json").read_text())
        by = {l["key"]: l for l in home["leagues"]}
        assert [g["id"] for g in by["nhl"]["games"]] == [1]                    # only the days around today
        assert [g["id"] for g in by["wvb"]["games"]] == [3]                    # college: only games with a ranked team
        assert by["wvb"]["games"][0]["away"] == ["a", "Away", 5, 1] and by["wvb"]["poll"] == "AVCA coaches poll"
        assert not by["cfb"]["ready"] and [s["ready"] for s in home["sports"]] == [True, True, False]
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
        assert [g["id"] for g in json.loads((site / "home.json").read_text())["leagues"][1]["games"]] == [9]
        assert (site / "volleyball" / "data.json").exists()
    print("PASS tools.assemble")
    return 0


if __name__ == "__main__":
    sys.exit(main())

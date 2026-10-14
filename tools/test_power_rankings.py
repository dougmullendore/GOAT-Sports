"""Checks for tools/power_rankings.py (no network). Run with:  python -m tools.test_power_rankings"""
import json
import sys
import tempfile
from pathlib import Path

from . import power_rankings as pr

TEAMS = [(str(i), f"City{i} Team{i}", f"Team{i}") for i in range(1, 21)]


def page(rows, noise=""):
    return "<html><body>" + noise + "".join(f"<h2>{n}. <a>{name}</a></h2><p>Record: 3-1. Previous ranking: 7</p>" for n, name in rows) + "</body></html>"


def main() -> int:
    top = [(n, f"City{n} Team{n}") for n in range(1, 21)]
    assert pr.order(page(top), TEAMS) == [[n, str(n)] for n in range(1, 21)]                       # written top first
    assert pr.order(page(list(reversed(top))), TEAMS) == [[n, str(n)] for n in range(1, 21)]         # written from the bottom up
    # a scoreboard before the article ("1 Team9 ... 3 Team4") does not get into the ranking
    noise = "<div>1 Team9 24 3 Team4 17</div>"
    assert pr.order(page(top, noise), TEAMS)[:2] == [[1, "1"], [2, "2"]]
    # a site that writes "Rank 6, up 4, Team6"
    ranked = "".join(f"<div>Rank {n}</div><div>up {n % 3} </div><h3>City{n} Team{n}</h3>" for n in range(1, 21))
    assert pr.order(ranked, TEAMS, "rank") == [[n, str(n)] for n in range(1, 21)]
    assert pr.when("2026-10-13 09:00:00 UTC").isoformat() == "2026-10-13T09:00:00+00:00"
    assert pr.when("2026-10-13T00:24:05-04:00").utcoffset().total_seconds() == -4 * 3600
    # college football's teams come from its list of FBS teams
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "data.json").write_text(json.dumps({"fbs": [["61", "Georgia", "SEC", {}], ["333", "Alabama", "SEC", {}]]}))
        (Path(d) / "data.json").write_text(json.dumps({"fbs": [["61", "Georgia", "SEC", {}], ["344", "Mississippi State", "SEC", {}]]}))
        teams = pr.league_teams(Path(d))
        assert teams[0] == ("61", "Georgia", "Georgia") and teams[1][:3] == ("344", "Mississippi State", "Mississippi State")
    # "Miss State" and "Mississippi St" are Mississippi State
    assert pr.order(page([(1, "Georgia"), (2, "Miss State")]), teams) == [[1, "61"], [2, "344"]]
    assert pr.LEAGUES["cfb"][0] == "football" and pr.LEAGUES["cbb"] == ("basketball", pr.LEAGUES["cfb"][1])
    assert set(pr.COLLEGE) == set(pr.ESPN_COLLEGE) == {"cfb", "cbb"} and all(set(pr.COLLEGE[lg]) | {"espn"} == set(pr.LEAGUES[lg][1]) for lg in pr.COLLEGE)
    # ESPN's rankings of something other than teams are passed over
    assert pr.NOT_A_RANKING.search("Ranking college football's top 25 freshmen") and not pr.NOT_A_RANKING.search("College football Power Rankings: Week 6")
    # a numbered list whose numbers are the list's own: read in order, a note after a name allowed
    listed = "<ol>" + "".join(f"<li>City{n} Team{n}{' (new)' if n == 3 else ''}</li>" for n in range(1, 21)) + "</ol>"
    assert pr.order_list(listed, TEAMS) == [[n, str(n)] for n in range(1, 21)]
    assert pr.norm("St. John’s") == pr.norm("St. John's") == "st johns"
    # every source a league reads has a name to show, and a fixed article belongs to a source the league reads
    assert all(s in pr.LABELS for _, srcs in pr.LEAGUES.values() for s in srcs)
    assert all(s in pr.LEAGUES[lg][1] for lg in pr.FIXED for s in pr.FIXED[lg])
    print("PASS tools.power_rankings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
